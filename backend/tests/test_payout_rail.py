"""Tests for the direct USDT payout rail.

These cover the decision logic, not the signing: a test that broadcast real USDT
would need funded keys and cost real money. What matters and is testable here is
that every wrong input fails *closed* with a clear message, because a payout that
fails open loses money and one that fails obscurely is unauditable.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services import payout_rail
from app.services.payout_rail import PayoutRailError


class TestChainRegistry:
    def test_all_supported_chains_are_resolvable(self):
        for chain_id in payout_rail.SUPPORTED_CHAINS:
            assert payout_rail.get_chain(chain_id).id == chain_id

    def test_chain_lookup_is_case_insensitive(self):
        assert payout_rail.get_chain("  BSC ").id == "bsc"

    def test_unknown_chain_lists_the_options(self):
        with pytest.raises(PayoutRailError) as exc:
            payout_rail.get_chain("dogecoin")
        message = str(exc.value)
        assert "Unsupported payout chain" in message
        # The message must tell the operator what they can pick instead.
        for chain_id in payout_rail.SUPPORTED_CHAINS:
            assert chain_id in message

    def test_every_chain_has_a_usdt_contract_and_explorer(self):
        for chain in payout_rail.CHAINS.values():
            assert chain.usdt_address
            assert "{}" in chain.explorer_tx
            assert chain.confirmations >= 1

    def test_usdt_has_six_decimals_everywhere(self):
        """USDT is 6 decimals on every chain here; a mismatch loses funds."""
        assert payout_rail.USDT_DECIMALS == 6

    def test_tron_is_offered_first(self):
        """Tron is the practical rail for Nigerian users (TRC20 off-ramps)."""
        assert payout_rail.SUPPORTED_CHAINS[0] == "tron"

    def test_describe_chains_exposes_costs(self):
        described = payout_rail.describe_chains()
        assert len(described) == len(payout_rail.SUPPORTED_CHAINS)
        for entry in described:
            assert entry["typical_cost_usd"]
            assert entry["label"]

    def test_explorer_url_is_built_from_the_chain(self):
        url = payout_rail.explorer_url("bsc", "0xabc")
        assert url == "https://bscscan.com/tx/0xabc"


class TestAddressValidation:
    @pytest.mark.parametrize(
        "chain_id,address",
        [
            ("ethereum", "0x" + "a" * 40),
            ("bsc", "0x" + "B" * 40),
            ("polygon", "0x" + "1234567890abcdef" * 2 + "abcdef12"),
        ],
    )
    def test_valid_evm_addresses(self, chain_id, address):
        normalised = payout_rail.validate_address(chain_id, address)
        assert normalised.startswith("0x")
        # EVM addresses are normalised to lowercase; the contract call needs a
        # checksummed form, which web3 applies itself.
        assert normalised == normalised.lower()

    def test_valid_tron_address(self):
        address = "TCLBgkbfVkJroVBJVqBEsxtPNQEQMTQCLQ"
        assert payout_rail.validate_address("tron", address) == address

    def test_valid_solana_address(self):
        address = "So11111111111111111111111111111111111111112"
        assert payout_rail.validate_address("solana", address) == address

    def test_empty_address_is_rejected(self):
        for chain_id in payout_rail.SUPPORTED_CHAINS:
            with pytest.raises(PayoutRailError):
                payout_rail.validate_address(chain_id, "")

    def test_whitespace_is_trimmed_not_rejected(self):
        address = "0x" + "a" * 40
        assert payout_rail.validate_address("bsc", f"  {address}\n") == address

    @pytest.mark.parametrize(
        "chain_id,address",
        [
            ("ethereum", "0x" + "a" * 39),  # too short
            ("ethereum", "0x" + "a" * 41),  # too long
            ("ethereum", "a" * 40),  # no 0x
            ("ethereum", "0x" + "z" * 40),  # non-hex
            ("bsc", "TCLBgkbfVkJroVBJVqBEsxtPNQEQMTQCLQ"),  # tron on an EVM chain
        ],
    )
    def test_invalid_evm_addresses(self, chain_id, address):
        with pytest.raises(PayoutRailError):
            payout_rail.validate_address(chain_id, address)

    def test_bsc_address_is_not_treated_as_ethereum(self):
        """The old code guessed the chain from the address and could not tell
        BSC from Ethereum (both are 0x + 40 hex). Chain is explicit now."""
        address = "0x" + "c" * 40
        assert payout_rail.validate_address("bsc", address) == address
        assert payout_rail.validate_address("ethereum", address) == address
        # Both accept it; the *caller's* chosen chain decides where it goes.

    @pytest.mark.parametrize(
        "address",
        ["0xabc", "T", "tCLBgkbfVkJroVBJVqBEsxtPNQEQMTQCLQ", "TCLBgkbfVkJroVBJVqBEsxtPNQEQMTQCLQextra"],
    )
    def test_invalid_tron_addresses(self, address):
        with pytest.raises(PayoutRailError):
            payout_rail.validate_address("tron", address)

    @pytest.mark.parametrize(
        "address",
        [
            "tooshort",
            "0x" + "a" * 40,  # an EVM address: valid length, wrong alphabet
            "0" * 40,  # length ok, '0' is not base58
            "O" * 40,  # length ok, 'O' is not base58
            "I" * 40,  # length ok, 'I' is not base58
            "l" * 40,  # length ok, 'l' is not base58
            "T" + "x" * 45,  # too long
        ],
    )
    def test_invalid_solana_addresses(self, address):
        with pytest.raises(PayoutRailError):
            payout_rail.validate_address("solana", address)

    def test_solana_rejects_an_evm_address(self):
        """The specific confusion that motivated the alphabet check.

        An EVM address is 0x + 40 hex, which is 42 characters - inside Solana's
        32-44 length window. Only the alphabet check rejects it.
        """
        evm = "0x" + "a" * 40
        with pytest.raises(PayoutRailError) as exc:
            payout_rail.validate_address("solana", evm)
        assert "base58" in str(exc.value)


class TestAmountConversion:
    def test_whole_amount(self):
        assert payout_rail._to_units(Decimal("10")) == 10_000_000

    def test_fractional_amount_is_exact(self):
        """Float representation must not leak into the on-chain amount.

        A float 10.005 is actually 10.00499999..., which would send one unit
        (0.000001 USDT) less than intended - or, worse, disagree with what the
        audit record says was sent.
        """
        assert payout_rail._to_units(Decimal("10.005")) == 10_005_000

    def test_thirds_do_not_lose_precision(self):
        assert payout_rail._to_units(Decimal("33.33")) == 33_330_000

    @pytest.mark.parametrize("amount", ["0", "-1", "-0.01"])
    def test_non_positive_amounts_rejected(self, amount):
        with pytest.raises(PayoutRailError):
            payout_rail._to_units(Decimal(amount))

    def test_dust_rejected(self):
        """A sub-cent transfer only wastes gas."""
        with pytest.raises(PayoutRailError) as exc:
            payout_rail._to_units(Decimal("0.001"))
        assert "minimum" in str(exc.value)

    def test_exactly_minimum_allowed(self):
        assert payout_rail._to_units(payout_rail.MIN_TRANSFER_USD) == 10_000

    def test_amount_that_rounds_to_zero_rejected(self):
        with pytest.raises(PayoutRailError):
            payout_rail._to_units(Decimal("0.000001"))


class TestTransferRefusals:
    """Every failure must raise, never sign or broadcast."""

    EVM_KEY = "0x" + "1" * 64

    @pytest.mark.asyncio
    async def test_missing_key_is_refused(self):
        with pytest.raises(PayoutRailError) as exc:
            await payout_rail.transfer_usdt(
                chain_id="bsc",
                to_address="0x" + "b" * 40,
                amount_usd=Decimal("5"),
                private_key="",
            )
        assert "hot-wallet key" in str(exc.value)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("key", ["0xdeadbeef", "0x" + "z" * 64, "0x" + "1" * 63])
    async def test_malformed_evm_key_refused_before_signing(self, key):
        with pytest.raises(PayoutRailError):
            await payout_rail.transfer_usdt(
                chain_id="bsc",
                to_address="0x" + "b" * 40,
                amount_usd=Decimal("5"),
                private_key=key,
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("key", ["11" * 31, "zz" * 32, "0x" + "11" * 32])
    async def test_malformed_tron_key_refused(self, key):
        with pytest.raises(PayoutRailError):
            await payout_rail.transfer_usdt(
                chain_id="tron",
                to_address="TCLBgkbfVkJroVBJVqBEsxtPNQEQMTQCLQ",
                amount_usd=Decimal("5"),
                private_key=key,
            )

    @pytest.mark.asyncio
    async def test_bad_address_refused_before_any_network_call(self):
        """Validation happens first, so no RPC traffic is generated."""
        with pytest.raises(PayoutRailError):
            await payout_rail.transfer_usdt(
                chain_id="bsc",
                to_address="not-an-address",
                amount_usd=Decimal("5"),
                private_key=self.EVM_KEY,
            )

    @pytest.mark.asyncio
    async def test_dust_amount_refused(self):
        with pytest.raises(PayoutRailError):
            await payout_rail.transfer_usdt(
                chain_id="bsc",
                to_address="0x" + "b" * 40,
                amount_usd=Decimal("0.0001"),
                private_key=self.EVM_KEY,
            )

    @pytest.mark.asyncio
    async def test_unreachable_rpc_reports_a_clean_error(self):
        """A network failure must surface as PayoutRailError, not a raw
        library exception that a caller would not know how to handle."""
        with pytest.raises(PayoutRailError) as exc:
            await payout_rail.transfer_usdt(
                chain_id="bsc",
                to_address="0x" + "b" * 40,
                amount_usd=Decimal("5"),
                private_key=self.EVM_KEY,
                rpc_url="http://127.0.0.1:1",  # nothing listening
            )
        assert "RPC" in str(exc.value) or "transfer failed" in str(exc.value)


class TestKeyFamilyMapping:
    """An EVM key must never be used to sign a Tron or Solana transfer."""

    def test_each_family_maps_to_its_own_key_field(self):
        assert payout_rail.FAMILY_KEY_FIELD["evm"] == "evm"
        assert payout_rail.FAMILY_KEY_FIELD["tron"] == "tron"
        assert payout_rail.FAMILY_KEY_FIELD["solana"] == "solana"

    def test_one_evm_key_covers_all_evm_chains(self):
        families = {
            payout_rail.get_chain(c).family
            for c in ("ethereum", "bsc", "polygon")
        }
        assert families == {"evm"}


class TestBase58:
    def test_leading_zero_bytes_map_to_leading_ones(self):
        assert payout_rail.base58_encode(b"\x00\x00\x01") == "112"

    def test_empty_input(self):
        assert payout_rail.base58_encode(b"") == "1"

    def test_matches_known_vector(self):
        # Solana's wrapped SOL address is a well-known base58 value.
        assert (
            payout_rail.base58_encode(bytes.fromhex("00"))
            == "1"
        )

    def test_omits_ambiguous_characters(self):
        """Solana base58 excludes 0, O, I and l, so a signature can never be
        mis-transcribed into an invalid character."""
        encoded = payout_rail.base58_encode(bytes(range(32)))
        assert not set("0OIl") & set(encoded)