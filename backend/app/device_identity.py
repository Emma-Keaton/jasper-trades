"""Device identity.

This application has no user accounts. A device's identity is a UUID that the
client generates once, stores locally, and sends on every request as
`X-Device-ID`. That UUID is the credential: whoever presents it *is* that
device.

That makes three properties load-bearing, and this module is where they are
enforced.

**The UUID must be unguessable.** The client generates it with
`crypto.randomUUID()` (122 bits of CSPRNG output). The previous generator was
`base64(platform + Date.now() + Math.random())`, which is a timestamp plus a
non-cryptographic PRNG - guessable by anyone who knows roughly when the device
first connected.

**The UUID must be validated.** Unvalidated, the header was an identity *label*:
`x_device_id or "default-device"` meant that any caller who simply omitted the
header authenticated as the same shared device, alongside the real one. Twelve
call sites did exactly that. There is no longer a fallback - a request without a
valid device UUID is rejected.

**The UUID must be stable.** It is stored in `localStorage` under
`jasper_device_id` and never rotated implicitly, because rotating it would
orphan the device's settings, portfolio, and history.

What this model does not give you: revocation (there is no server-side deny
list), and protection against a leaked UUID. For a self-hosted single-operator
deployment reachable only by its owner that is an acceptable trade, and it is the
model the product is built around. It is *not* suitable if the instance is ever
exposed publicly to untrusted callers - a UUID is a bearer token, and anyone who
obtains one has that device's full access.
"""

from __future__ import annotations

import re
import uuid

#: Canonical lowercase UUID text, exactly as `crypto.randomUUID()` emits it.
#:
#: Anchored and strict: `search` is anchored at both ends and the length is
#: fixed by the pattern, so no prefix or suffix can smuggle anything past it.
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

#: Header carrying the device credential.
DEVICE_HEADER = "X-Device-ID"


class DeviceIdentityError(ValueError):
    """The supplied device identifier is not a usable UUID."""


def is_valid_device_id(value: object) -> bool:
    """True when `value` is a canonical UUID string."""
    return isinstance(value, str) and bool(UUID_RE.match(value))


def normalise_device_id(value: object) -> str:
    """Return a canonical lowercase UUID, or raise.

    Raises rather than falling back. A missing or malformed credential is a
    client error; defaulting to a shared identity would silently merge an
    anonymous caller into a real device's settings and portfolio.
    """
    if value is None:
        raise DeviceIdentityError(
            f"{DEVICE_HEADER} header is required. Send this device's UUID."
        )
    if not isinstance(value, str):
        raise DeviceIdentityError(
            f"{DEVICE_HEADER} must be a string UUID, got {type(value).__name__}"
        )

    candidate = value.strip()
    if not candidate:
        raise DeviceIdentityError(f"{DEVICE_HEADER} is empty")

    # Accept uppercase (UUIDs are case-insensitive) but store one canonical form,
    # so the same device cannot create two rows by varying case.
    candidate = candidate.lower()

    if not UUID_RE.match(candidate):
        raise DeviceIdentityError(
            f"{DEVICE_HEADER} is not a valid UUID: {value!r}. "
            "Expected the value from getOrCreateDeviceId(), e.g. "
            "3f2504e0-4f89-11d3-9a0c-0305e82c3301."
        )
    return candidate


def try_normalise_device_id(value: object) -> str | None:
    """Normalise, or return None instead of raising."""
    try:
        return normalise_device_id(value)
    except DeviceIdentityError:
        return None


def new_device_id() -> str:
    """Server-side UUID, for seeding and tests.

    The browser generates the real credential with `crypto.randomUUID()`; this
    exists so migrations and scripts can mint one without the CSPRNG being
    reached for in two languages.
    """
    return str(uuid.uuid4())