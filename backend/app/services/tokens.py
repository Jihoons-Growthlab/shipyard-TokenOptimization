"""JWT 발급·검증."""
import time
import uuid

import jwt

from .. import config, errors


def issue(sub: str, stage: str, ttl: int, **extra) -> str:
    now = int(time.time())
    claims = {"sub": sub, "stage": stage, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex, **extra}
    return jwt.encode(claims, config.APP_SECRET, algorithm="HS256")


def decode(token: str, stage: str) -> dict:
    try:
        claims = jwt.decode(token, config.APP_SECRET, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise errors.unauthorized() from None
    if claims.get("stage") != stage:
        raise errors.unauthorized()
    return claims
