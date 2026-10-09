"""FastAPI dependency for the device credential.

Every device-scoped route should take `device_id: str = Depends(require_device_id)`
rather than reading the header itself. Centralising it means the validation rule
exists once: a missing or malformed `X-Device-ID` is a 401, and there is no code
path that quietly substitutes a shared default identity.

See `app/device_identity.py` for why the device UUID is the credential and what
this model does and does not protect against.
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.device_identity import (
    DEVICE_HEADER,
    DeviceIdentityError,
    normalise_device_id,
)


def require_device_id(x_device_id: str | None = Header(None)) -> str:
    """Resolve and validate the calling device's UUID.

    Raises 401 when the credential is absent or malformed. Use this on every
    route that reads or writes device-scoped data.
    """
    try:
        return normalise_device_id(x_device_id)
    except DeviceIdentityError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_device_id",
                "message": str(exc),
                "header": DEVICE_HEADER,
            },
        ) from exc


def optional_device_id(x_device_id: str | None = Header(None)) -> str | None:
    """Resolve the device UUID when present, without rejecting.

    For endpoints that are meaningful for anonymous callers (health, status) but
    behave better when they know the device. Never returns a placeholder identity.
    """
    if x_device_id is None:
        return None
    try:
        return normalise_device_id(x_device_id)
    except DeviceIdentityError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_device_id",
                "message": str(exc),
                "header": DEVICE_HEADER,
            },
        ) from exc