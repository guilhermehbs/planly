import base64
import hashlib
import hmac
import os


def hash_password(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"{base64.b64encode(salt).decode()}:{base64.b64encode(digest).decode()}"


def verify_password(password, stored):
    try:
        salt_text, digest_text = stored.split(":", 1)
        salt = base64.b64decode(salt_text.encode())
        expected = base64.b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False
