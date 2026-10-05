import hashlib, hmac, os, secrets
from datetime import datetime, timedelta, timezone
import jwt
SECRET = os.environ["JWT_SECRET"]
if len(SECRET) < 32 or SECRET.startswith("replace-"):
    raise RuntimeError("Set JWT_SECRET to a random secret of at least 32 characters")
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"
def verify_password(password: str, stored: str) -> bool:
    try:
        kind, salt, expected = stored.split("$")
        if kind != "scrypt": return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError): return False
def token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=8), "iss": "smart-parking"}, SECRET, algorithm="HS256")
