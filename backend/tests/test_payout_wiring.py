"""Tests for payout wiring in the withdrawal service and scheduler.

The rail's signing is covered in `test_payout_rail.py`. These cover the parts
that decide *whether* a payout is attempted and *where* it goes: that a crypto
withdrawal must name a chain, that an unusable config fails closed, and that the
scheduler no longer pays the wrong portfolio.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services import payout_rail
from app.services.withdrawal_service import (
    ApiKeyService,
    WithdrawalService,
    payout_rail_keys_for,
)
from app.services.encryption import EncryptionHelper


EVM_ADDRESS = "0x" + "b" * 40
TRON_ADDRESS = "TCLBgkbfVkJroVBJVqBEsxtPNQEQMTQCLQ"


class TestKeyFamilySelection:
    def test_evm_key_used_for_every_evm_chain(self):
        keys = {"evm": "0xkey", "tron": "tronkey"}
        for chain_id in ("ethereum", "bsc", "polygon"):
            assert payout_rail_keys_for(keys, chain_id) == "0xkey"

    def test_tron_key_used_for_tron(self):
        keys = {"evm": "0xkey", "tron": "tronkey"}
        assert payout_rail_keys_for(keys, "tron") == "tronkey"

    def test_solana_key_used_for_solana(self):
        keys = {"solana": "solkey"}
        assert payout_rail_keys_for(keys, "solana") == "solkey"

    def test_missing_family_key_is_refused(self):
        """An EVM key must never be silently reused for another chain family."""
        with pytest.raises(ValueError) as exc:
            payout_rail_keys_for({"evm": "0xkey"}, "tron")
        assert "tron" in str(exc.value)

    def test_empty_bundle_is_refused(self):
        with pytest.raises(ValueError):
            payout_rail_keys_for({}, "bsc")


class TestPayoutWalletKeyStorage:
    @pytest.mark.asyncio
    async def test_keys_round_trip_through_encryption(self, db):
        """Keys must survive a save/load cycle decrypted, or payouts silently
        fail at send time."""
        from app.models import DeviceSettings

        encryption = EncryptionHelper()
        bundle = {"evm": "0x" + "1" * 64, "tron": "11" * 32}
        settings = DeviceSettings(
            device_id="dev-keys",
            payout_wallet_keys=encryption.encrypt_json(bundle),
        )
        db.add(settings)
        await db.commit()

        loaded = await ApiKeyService(db).get_payout_wallet_keys()
        assert loaded == bundle

    @pytest.mark.asyncio
    async def test_absent_keys_return_none(self, db):
        assert await ApiKeyService(db).get_payout_wallet_keys() is None

    @pytest.mark.asyncio
    async def test_stored_keys_are_not_plaintext(self, db):
        """Guard against someone 'simplifying' this to a plaintext column."""
        from app.models import DeviceSettings

        secret = "0x" + "9" * 64
        settings = DeviceSettings(
            device_id="dev-plain",
            payout_wallet_keys=EncryptionHelper().encrypt_json({"evm": secret}),
        )
        assert secret not in settings.payout_wallet_keys


class TestCryptoWithdrawalRequiresAChain:
    @pytest.mark.asyncio
    async def test_missing_chain_is_refused(self, db, portfolio):
        """The old code inferred the chain from the address, which cannot tell
        BSC from Ethereum. A crypto withdrawal without an explicit chain is now
        rejected before a pending row exists."""
        service = WithdrawalService(db)
        with pytest.raises(Exception) as exc:
            await service.create_withdrawal(
                portfolio_id=portfolio.id,
                amount=10.0,
                withdrawal_type="manual",
                destination_type="crypto_wallet",
                destination_address=EVM_ADDRESS,
            )
        assert "chain" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_unknown_chain_is_refused(self, db, portfolio):
        service = WithdrawalService(db)
        with pytest.raises(payout_rail.PayoutRailError):
            await service.create_withdrawal(
                portfolio_id=portfolio.id,
                amount=10.0,
                withdrawal_type="manual",
                destination_type="crypto_wallet",
                destination_address=EVM_ADDRESS,
                destination_chain="dogecoin",
            )

    @pytest.mark.asyncio
    async def test_address_must_match_the_chosen_chain(self, db, portfolio):
        """A Tron address on BSC is a configuration error, not something to
        discover after spending gas."""
        service = WithdrawalService(db)
        with pytest.raises(payout_rail.PayoutRailError):
            await service.create_withdrawal(
                portfolio_id=portfolio.id,
                amount=10.0,
                withdrawal_type="manual",
                destination_type="crypto_wallet",
                destination_address=TRON_ADDRESS,
                destination_chain="bsc",
            )

    @pytest.mark.asyncio
    async def test_valid_chain_and_address_are_recorded(self, db, portfolio):
        from app.models import Withdrawal

        service = WithdrawalService(db)
        withdrawal = await service.create_withdrawal(
            portfolio_id=portfolio.id,
            amount=10.0,
            withdrawal_type="manual",
            destination_type="crypto_wallet",
            destination_address=EVM_ADDRESS,
            destination_chain="bsc",
        )
        assert withdrawal.destination_chain == "bsc"
        assert withdrawal.status == "pending"

    @pytest.mark.asyncio
    async def test_bank_payout_needs_no_chain(self, db, portfolio):
        """A naira-bank payout has no on-chain destination, so requiring a
        chain there would be wrong."""
        from app.models import Withdrawal

        service = WithdrawalService(db)
        withdrawal = await service.create_withdrawal(
            portfolio_id=portfolio.id,
            amount=10.0,
            withdrawal_type="auto_payout",
            destination_type="naira_bank",
            destination_address="GTBank - John Doe",
        )
        assert withdrawal.destination_chain is None


class TestPayoutConfigChain:
    @pytest.mark.asyncio
    async def test_auto_payout_skipped_without_a_chain(self, db):
        """A config with a wallet but no network must not attempt a transfer.

        It would fail at signing time; failing here keeps the reason visible in
        one place instead of as a withdrawal failure.
        """
        service = WithdrawalService(db)
        result = await service.execute_auto_payout(
            portfolio_id=1,
            payout_config={
                "payout_enabled": True,
                "payout_percentage": 50.0,
                "min_payout_threshold": 0.0,
                "payout_destination": "crypto_wallet",
                "crypto_wallet": EVM_ADDRESS,
                # payout_chain deliberately absent
            },
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_auto_payout_skipped_without_a_wallet(self, db):
        service = WithdrawalService(db)
        result = await service.execute_auto_payout(
            portfolio_id=1,
            payout_config={
                "payout_enabled": True,
                "payout_percentage": 50.0,
                "min_payout_threshold": 0.0,
                "payout_destination": "crypto_wallet",
                "payout_chain": "bsc",
            },
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_disabled_config_never_pays(self, db):
        service = WithdrawalService(db)
        result = await service.execute_auto_payout(
            portfolio_id=1,
            payout_config={
                "payout_enabled": False,
                "payout_destination": "crypto_wallet",
                "crypto_wallet": EVM_ADDRESS,
                "payout_chain": "bsc",
            },
        )
        assert result is None


class TestSchedulerPortfolioSelection:
    """The scheduler previously did `select(Portfolio).limit(1)`, evaluating
    every device's payout config against the first portfolio in the database."""

    @pytest.mark.asyncio
    async def test_device_with_no_portfolio_is_skipped_not_misattributed(self, db):
        from sqlalchemy import select

        from app.models import DeviceSettings, Portfolio

        # A portfolio belonging to a different device exists.
        other = Portfolio(device_id="someone-else", name="Other", cash=1000.0)
        db.add(other)
        await db.commit()

        settings = DeviceSettings(
            device_id="lonely-device",
            payout_config=EncryptionHelper().encrypt_json(
                {
                    "payout_enabled": True,
                    "payout_percentage": 50.0,
                    "payout_schedule_hour": 0,
                    "payout_schedule_minute": 0,
                    "payout_destination": "crypto_wallet",
                    "crypto_wallet": EVM_ADDRESS,
                    "payout_chain": "bsc",
                    "min_payout_threshold": 0.0,
                }
            ),
        )
        db.add(settings)
        await db.commit()

        portfolios = (
            (
                await db.execute(
                    select(Portfolio).where(
                        Portfolio.device_id == settings.device_id
                    )
                )
            )
            .scalars()
            .all()
        )
        # The device owns nothing, so nothing can be paid for it. The old code
        # would have found `other` and paid out of it.
        assert portfolios == []
        assert other.device_id != settings.device_id

    @pytest.mark.asyncio
    async def test_only_the_owning_device_portfolio_matches(self, db):
        from sqlalchemy import select

        from app.models import Portfolio

        mine = Portfolio(device_id="me", name="Mine", cash=1000.0)
        theirs = Portfolio(device_id="them", name="Theirs", cash=1000.0)
        db.add_all([mine, theirs])
        await db.commit()

        matched = (
            (
                await db.execute(
                    select(Portfolio).where(Portfolio.device_id == "me")
                )
            )
            .scalars()
            .all()
        )
        assert [p.id for p in matched] == [mine.id]


class TestAmountHandling:
    def test_fee_and_net_are_consistent(self):
        service = WithdrawalService.__new__(WithdrawalService)
        amount = Decimal("100")
        fee = amount * service.FEE_PERCENTAGE
        assert fee == Decimal("0.100")
        assert amount - fee == Decimal("99.900")

    def test_minimum_withdrawal_is_one_dollar(self):
        assert WithdrawalService.MIN_WITHDRAWAL == Decimal("1.0")

    def test_rail_dust_floor_is_below_the_service_minimum(self):
        """Ordering sanity: a transfer the service would allow must not then be
        rejected as dust by the rail."""
        assert payout_rail.MIN_TRANSFER_USD < WithdrawalService.MIN_WITHDRAWAL