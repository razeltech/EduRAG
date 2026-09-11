from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config_load import CONFIG_PATH, load_config

PBKDF_ROUNDS = 120_000
ALGO = "HS256"


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF_ROUNDS
    )
    return f"pbkdf2${PBKDF_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        kind, rounds, salt, digest = stored.split("$", 3)
        if kind != "pbkdf2":
            return False
        check = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(rounds)
        )
        return hmac.compare_digest(check.hex(), digest)
    except (ValueError, TypeError):
        return False


def jwt_secret() -> str:
    cfg = load_config()
    auth = cfg.get("auth") or {}
    secret = auth.get("jwt_secret")
    if secret:
        return str(secret)
    secret = secrets.token_hex(32)
    import yaml

    cfg = load_config()
    cfg.setdefault("auth", {})["jwt_secret"] = secret
    CONFIG_PATH.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return secret


def make_token(user: dict, hours: int = 24, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "role": user["role"],
        "inst": user["institution_id"],
        "exp": now + timedelta(hours=hours),
        "iat": now,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, jwt_secret(), algorithm=ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, jwt_secret(), algorithms=[ALGO])
