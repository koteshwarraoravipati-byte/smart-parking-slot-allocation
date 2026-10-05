from app.security import hash_password, verify_password, token, SECRET
import jwt
def test_password_hash():
    first = hash_password("a-strong-test-password")
    assert first != hash_password("a-strong-test-password")
    assert verify_password("a-strong-test-password", first)
    assert not verify_password("wrong", first)
    assert not verify_password("wrong", "broken")
def test_token():
    claims = jwt.decode(token(7),SECRET,algorithms=["HS256"],issuer="smart-parking")
    assert claims["sub"] == "7"
    assert claims["exp"] > claims["iat"]
