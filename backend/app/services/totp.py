"""RFC 6238 TOTP (SHA1, 6자리, 30초, ±1 step)."""
import base64
import hashlib
import hmac
import struct
import time

STEP = 30
WINDOW = 1


def code_at(secret: str, counter: int) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def matching_step(secret: str, code: str, now: float | None = None) -> int | None:
    current = int((time.time() if now is None else now) // STEP)
    for counter in range(current - WINDOW, current + WINDOW + 1):
        if hmac.compare_digest(code_at(secret, counter), code):
            return counter
    return None
