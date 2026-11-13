from . import config
import base64
import hashlib
import hmac
import json
import os
import time

JWT_SECRET = config.get("JWT_SECRET")
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be configured with at least 32 characters.")
SECRET = JWT_SECRET.encode()
OWNER_EMAIL = config.get("OWNER_EMAIL").strip().lower()
OWNER_PASSWORD_HASH = config.get("OWNER_PASSWORD_HASH").strip()


def _b(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _u(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_pw(password, salt=None):
    salt = salt or os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return salt.hex() + "$" + derived.hex()


def check_pw(password, stored):
    try:
        salt, expected = stored.split("$", 1)
        actual = hash_pw(password, bytes.fromhex(salt)).split("$", 1)[1]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def authenticate(email, password):
    if not OWNER_EMAIL or not OWNER_PASSWORD_HASH:
        return None
    if not hmac.compare_digest(email.strip().lower(), OWNER_EMAIL):
        return None
    if not check_pw(password, OWNER_PASSWORD_HASH):
        return None
    return {"sub": OWNER_EMAIL, "role": "admin"}


def make_token(user, role, ttl=3600):
    header = _b(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b(json.dumps({"sub": user, "role": role, "exp": time.time() + ttl}).encode())
    signature = _b(hmac.new(SECRET, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def verify(token):
    try:
        header, payload, signature = token.split(".")
        expected = _b(hmac.new(SECRET, f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            return None
        claims = json.loads(_u(payload))
        if claims["exp"] <= time.time():
            return None
        if claims.get("sub") != OWNER_EMAIL or claims.get("role") != "admin":
            return None
        return claims
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
