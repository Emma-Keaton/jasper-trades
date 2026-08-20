"""Onboarding state endpoints backed by DeviceSettings.preferences."""
import json


async def test_onboarding_get_empty(app_client):
    resp = await app_client.get("/api/v1/settings/onboarding", headers={"X-Device-ID": "dev-1"})
    assert resp.status_code == 200
    assert resp.json() == {"onboarding": {}}


async def test_onboarding_get_missing_device_header(app_client):
    resp = await app_client.get("/api/v1/settings/onboarding")
    assert resp.status_code == 200
    assert resp.json() == {"onboarding": {}}


async def test_onboarding_save_and_read(app_client):
    patch = {"welcome_done": True, "onboarding_completed": False}
    save = await app_client.post(
        "/api/v1/settings/onboarding",
        json={"onboarding": patch},
        headers={"X-Device-ID": "dev-1"},
    )
    assert save.status_code == 200

    get = await app_client.get("/api/v1/settings/onboarding", headers={"X-Device-ID": "dev-1"})
    assert get.status_code == 200
    assert get.json()["onboarding"] == patch


async def test_onboarding_shallow_merge_per_key(app_client):
    await app_client.post(
        "/api/v1/settings/onboarding",
        json={"onboarding": {"step_1": True}},
        headers={"X-Device-ID": "dev-1"},
    )
    await app_client.post(
        "/api/v1/settings/onboarding",
        json={"onboarding": {"step_2": True}},
        headers={"X-Device-ID": "dev-1"},
    )
    get = await app_client.get("/api/v1/settings/onboarding", headers={"X-Device-ID": "dev-1"})
    assert get.json()["onboarding"] == {"step_1": True, "step_2": True}


async def test_onboarding_post_requires_device_header(app_client):
    resp = await app_client.post("/api/v1/settings/onboarding", json={"onboarding": {"x": True}})
    assert resp.status_code == 400


async def test_onboarding_persists_in_preferences(app_client, session_factory):
    await app_client.post(
        "/api/v1/settings/onboarding",
        json={"onboarding": {"done": True}},
        headers={"X-Device-ID": "dev-1"},
    )
    async with session_factory() as session:
        from sqlalchemy import select

        from app.models import DeviceSettings

        row = (await session.execute(select(DeviceSettings))).scalars().first()
        assert row is not None
        prefs = json.loads(row.preferences)
        assert prefs["onboarding"]["done"] is True