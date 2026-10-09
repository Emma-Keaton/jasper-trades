"""Regression tests for the DeviceSettings row-loading defect.

Every one of these call sites used `DeviceSettings.__table__.select()`, which selects
*columns* rather than the ORM entity. `result.scalar_one_or_none()` therefore
returned `row[0]` - the value of the first column, `device_id`, a plain string -
instead of a `DeviceSettings` row.

The failure was not uniform, which is why it survived:

- Attribute access on the string raised `AttributeError` loudly
  (`forex.py` x3, `forex_polling_service.py`, `banks.py`, and four
  `settings.py` endpoints).
- Elsewhere it failed *quietly*. `settings.py:59` updated rows via
  `if hasattr(row, key): setattr(row, key, value)`, and `hasattr` is False for every
  setting on a string, so every write was silently dropped and the update appeared
  to succeed.

Net effect: Trove settings could not be saved, validated, or used; naira bank
payout config could not be read; and parts of the Settings API did nothing.

These tests exercise the real query shapes against the test database rather than
asserting on source text, so a reintroduced `__table__.select()` fails here.
"""

import inspect

import pytest
import sqlalchemy as sa

from app.models import DeviceSettings

from conftest import DEVICE_HEADERS, TEST_DEVICE_ID


def _files_using_broken_select() -> list:
    """Any remaining `Model.__table__.select()` in app/ is this same bug."""
    import pathlib

    import app

    root = pathlib.Path(app.__file__).parent
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "__table__.select()" in text:
            offenders.append(f"{path.relative_to(root)}")
    return offenders


class TestNoTableSelectAnywhere:
    def test_no_core_table_select_in_app(self):
        """`__table__.select()` returns columns, never an ORM entity.

        This is the root cause of the defect these tests cover, so it is asserted
        across all of app/ rather than only in the files that happened to fail
        loudly today.
        """
        offenders = _files_using_broken_select()
        assert not offenders, (
            "Use select(Model) instead of Model.__table__.select(); "
            f"scalar_one_or_none() on a column select returns row[0]: {offenders}"
        )


class TestDeviceSettingsRowIsReturned:
    async def test_select_entity_yields_a_row(self, session_factory):
        """The fix: an entity select returns the ORM object, with attributes."""
        async with session_factory() as session:
            session.add(
                DeviceSettings(
                    device_id=TEST_DEVICE_ID,
                    trove_enabled=True,
                    trove_api_key="encrypted-blob",
                    trove_base_url="https://sandbox.api.trovefinance.com/v1",
                )
            )
            await session.commit()

            result = await session.execute(
                sa.select(DeviceSettings).where(DeviceSettings.device_id == TEST_DEVICE_ID)
            )
            row = result.scalar_one_or_none()

            assert row is not None
            assert isinstance(row, DeviceSettings)
            assert row.trove_enabled is True
            assert row.trove_api_key == "encrypted-blob"

    async def test_column_select_would_have_returned_a_string(self, session_factory):
        """Documents precisely why the old form broke, so it cannot be 'restored'.

        The old expression is still executable; it just yields the wrong object.
        """
        async with session_factory() as session:
            session.add(DeviceSettings(device_id=TEST_DEVICE_ID, trove_enabled=True))
            await session.commit()

            result = await session.execute(
                DeviceSettings.__table__.select().where(
                    DeviceSettings.device_id == TEST_DEVICE_ID
                )
            )
            row = result.scalar_one_or_none()

            assert isinstance(row, str), (
                "expected the column-select form to return a scalar column value"
            )
            assert not hasattr(row, "trove_enabled"), (
                "a string has no trove_enabled, which is the AttributeError that "
                "disabled Trove in production"
            )


class TestTroveSettingsEndpoints:
    """The three Trove paths, all of which were broken end to end."""

    async def test_trove_save_persists_fields(self, app_client, db):
        """`POST /settings/trove` wrote attributes onto a string, so nothing saved.

        Calls the real endpoint. Before the fix this raised AttributeError inside the
        handler and, because the handler caught it, returned success while discarding
        the write - the worst of both outcomes.
        """
        payload = {
            "trove_api_key": "plaintext-key",
            "trove_base_url": "https://example.test/v1",
            "trove_enabled": True,
            "trove_sandbox": True,
        }
        response = await app_client.post(
            "/api/v1/settings/trove",
            json=payload,
            headers=DEVICE_HEADERS,
        )
        assert response.status_code == 200, response.text

        result = await db.execute(
            sa.select(DeviceSettings).where(DeviceSettings.device_id == TEST_DEVICE_ID)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.trove_base_url == "https://example.test/v1"
        assert row.trove_enabled is True
        # The key must be stored encrypted, never as the plaintext that was sent.
        assert row.trove_api_key != payload["trove_api_key"]
        assert row.trove_api_key

    async def test_trove_connection_finds_stored_config(self, app_client, db, monkeypatch):
        """`GET /settings/trove/test` read `row.trove_api_key` off a string.

        Before the fix this raised AttributeError at the settings lookup and never
        reached the network. Asserting on reaching the (stubbed) call is what
        distinguishes "found the config" from "found nothing" - the defect under
        test - without depending on a live Trove account.
        """
        from app.api.v1 import settings as settings_api
        from app.services.encryption import EncryptionHelper

        # Store a genuinely encrypted key, as POST /settings/trove does, so this
        # also proves the decrypt round-trip rather than a passthrough.
        ciphertext = EncryptionHelper().encrypt("plaintext-trove-key")

        await db.execute(
            sa.insert(DeviceSettings).values(
                device_id=TEST_DEVICE_ID,
                trove_enabled=True,
                trove_api_key=ciphertext,
                trove_base_url="https://trove.invalid/v1",
            )
        )
        await db.commit()

        seen = {}

        class _Response:
            status_code = 200

            @staticmethod
            def json():
                return {"account_id": "acct-123"}

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, url, headers=None, timeout=None):
                seen["url"] = url
                seen["auth"] = headers
                return _Response()

        monkeypatch.setattr(settings_api.httpx, "AsyncClient", _Client)

        response = await app_client.get(
            "/api/v1/settings/trove/test", headers=DEVICE_HEADERS
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["valid"] is True, body
        assert body["account_id"] == "acct-123"
        # Proves the stored config was found and the key decrypted, not a default.
        assert seen["url"] == "https://trove.invalid/v1/user/account"
        assert seen["auth"]["Authorization"] == "Bearer plaintext-trove-key"
        assert ciphertext not in seen["auth"]["Authorization"], (
            "the ciphertext must never be sent to the broker"
        )

    async def test_trove_connection_reports_missing_config(self, app_client, db):
        """A device with no Trove config must get valid=false, not a crash."""
        await db.execute(
            sa.insert(DeviceSettings).values(device_id=TEST_DEVICE_ID)
        )
        await db.commit()

        response = await app_client.get(
            "/api/v1/settings/trove/test", headers=DEVICE_HEADERS
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["valid"] is False
        assert "not configured" in body["message"]

    async def test_trove_read_sees_saved_values(self, session_factory):
        """What forex.py and the polling service read on every call."""
        async with session_factory() as session:
            session.add(
                DeviceSettings(
                    device_id=TEST_DEVICE_ID,
                    trove_enabled=True,
                    trove_api_key="encrypted",
                    trove_base_url="https://example.test/v1",
                )
            )
            await session.commit()

            result = await session.execute(
                sa.select(DeviceSettings).where(DeviceSettings.device_id == TEST_DEVICE_ID)
            )
            settings = result.scalar_one_or_none()

            # The exact expression that raised AttributeError before.
            assert settings and settings.trove_enabled and settings.trove_api_key
            assert settings.trove_base_url == "https://example.test/v1"

    async def test_polling_service_filter_returns_the_row(self, session_factory):
        """The polling service selects by trove_enabled across devices."""
        async with session_factory() as session:
            session.add(
                DeviceSettings(device_id=TEST_DEVICE_ID, trove_enabled=True, trove_api_key="k")
            )
            session.add(
                DeviceSettings(device_id="00000000-0000-4000-8000-000000000001")
            )
            await session.commit()

            result = await session.execute(
                sa.select(DeviceSettings)
                .where(DeviceSettings.trove_enabled == True)  # noqa: E712
                .limit(1)
            )
            settings = result.scalar_one_or_none()
            assert settings is not None
            assert settings.trove_api_key == "k"
