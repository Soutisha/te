"""Users, roles and tokens. Role is always read from the database, never trusted from the token."""
import hmac, hashlib, json, time
from sqlalchemy import select
from .. import auth as legacy
from .models import User

PERMISSIONS = {
    "admin": {"*"},
    "manager": {"workflow:run", "transfer:approve", "purchase:approve", "purchase:approve:high", "transfer:receive", "audit:read", "data:read", "vehicle:update"},
    "inventory_manager": {"workflow:run", "transfer:approve", "purchase:approve", "transfer:receive", "data:read", "vehicle:update"},
    "auditor": {"audit:read", "data:read"},
    "viewer": {"data:read"},
}
def can(role, perm): p = PERMISSIONS.get(role, set()); return "*" in p or perm in p

def create_user(s, email, password, role):
    if role not in PERMISSIONS: raise ValueError(f"unknown role {role!r}")
    email = email.strip().lower()
    if s.get(User, email): raise ValueError("user exists")
    s.add(User(email=email, pw_hash=legacy.hash_pw(password), role=role, active=True)); s.flush()

def bootstrap_owner(s):
    """Create the env-configured owner as admin (hash only; plaintext is never stored)."""
    if legacy.OWNER_EMAIL and legacy.OWNER_PASSWORD_HASH and not s.get(User, legacy.OWNER_EMAIL):
        s.add(User(email=legacy.OWNER_EMAIL, pw_hash=legacy.OWNER_PASSWORD_HASH, role="admin", active=True)); s.flush()

def login(s, email, password):
    u = s.get(User, (email or "").strip().lower())
    if not u or not u.active or not legacy.check_pw(password, u.pw_hash): return None
    return token(u.email)

def token(email, ttl=3600):
    h = legacy._b(b'{"alg":"HS256","typ":"JWT"}')
    p = legacy._b(json.dumps({"sub": email, "exp": time.time() + ttl, "v": 2}).encode())
    sig = legacy._b(hmac.new(legacy.SECRET, f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{sig}"

def resolve(s, tok):
    """Return (email, role) for a valid token and an active DB user, else None."""
    try:
        h, p, sig = tok.split(".")
        if not hmac.compare_digest(legacy._b(hmac.new(legacy.SECRET, f"{h}.{p}".encode(), hashlib.sha256).digest()), sig): return None
        c = json.loads(legacy._u(p))
        if c["exp"] <= time.time() or c.get("v") != 2: return None
        u = s.get(User, c["sub"])
        return (u.email, u.role) if u and u.active else None
    except (ValueError, KeyError, TypeError, json.JSONDecodeError): return None
