"""Stable client-side pseudonyms (spec R2): tags = HMAC(local salt, name).
Same repo -> same tag on every push; the server can never reverse a tag."""
import hashlib, hmac, os

DEFAULT_SALT_PATH = os.path.expanduser("~/.config/agent-cost-lens/salt")

def load_or_create_salt(path=None):
    path = path or DEFAULT_SALT_PATH
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    salt = os.urandom(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(salt)
    return salt

def tag(salt, name, prefix=""):
    return prefix + hmac.new(salt, name.encode(), hashlib.sha256).hexdigest()[:12]
