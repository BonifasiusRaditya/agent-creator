"""Account credentials: usernames, password hashing and connector tokens."""
import hashlib
import hmac
import os
import re
import secrets

from .errors import AppError

USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{2,31}")
TOKEN_PREFIX = "tf_"
# Hash used for unknown usernames so a failed sign-in takes the same time either way.
_DUMMY_SALT = secrets.token_hex(16)


def normalize_username(value):
    """Usernames are case-insensitive: stored and compared in lowercase."""
    if not isinstance(value, str):
        raise AppError("Choose a username of 3–32 letters, numbers, dots, dashes or underscores.", "INVALID_USERNAME")
    username = value.strip().lower()
    if not USERNAME.fullmatch(username):
        raise AppError("Choose a username of 3–32 letters, numbers, dots, dashes or underscores, starting with a letter or number.", "INVALID_USERNAME")
    return username


def validate_password(value):
    if not isinstance(value, str) or not 8 <= len(value) <= 200:
        raise AppError("Choose a password between 8 and 200 characters.", "INVALID_PASSWORD_FORMAT")
    return value


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32).hex()
    return digest, salt


def verify_password(password, user):
    """Constant-time check; `user` may be None for an unknown username."""
    if not isinstance(password, str) or len(password) > 200:
        password = ""
    salt = user["password_salt"] if user else _DUMMY_SALT
    digest, _ = hash_password(password, salt)
    return bool(user) and hmac.compare_digest(digest, user["password_hash"])


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_connector_token():
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def invite_code():
    """Shared registration code from the environment. Empty means registration is closed."""
    return os.environ.get("TRENDFORGE_INVITE_CODE", "").strip()


def is_admin(username):
    """Workspace admins manage shared settings (speech model, legacy provider keys)."""
    admins = {x.strip().lower() for x in os.environ.get("TRENDFORGE_ADMIN_USERNAMES", "").split(",") if x.strip()}
    return username in admins
