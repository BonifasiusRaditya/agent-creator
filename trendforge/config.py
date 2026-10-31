import json
import os
import secrets
import threading
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# Use one application-owned file, independent of the launcher's working directory.
# Existing process variables take precedence; values never enter public responses.
ENV_FILE = ROOT / ".env"


def load_environment(path=ENV_FILE):
    return load_dotenv(path, override=False, interpolate=False)


load_environment()
DATA = Path(os.environ.get("TRENDFORGE_DATA_DIR", ROOT / ".data")).resolve()
STATIC = Path(__file__).resolve().parent / "static"


class Settings:
    """Encrypted local configuration. Credentials never appear in public responses."""

    defaults = {
        "ai_engine": "workbuddy",
        "ai_base_url": "", "ai_model": "", "ai_api_key": "",
        "youtube_api_key": "", "pexels_api_key": "", "pixabay_api_key": "",
        "stock_provider": "pixabay", "speech_model": "base",
        "password_hash": "", "password_salt": "", "service_token": "",
    }
    env_names = {
        "ai_engine": "TRENDFORGE_AI_ENGINE",
        "ai_base_url": "AI_BASE_URL", "ai_model": "AI_MODEL", "ai_api_key": "AI_API_KEY",
        "youtube_api_key": "YOUTUBE_API_KEY", "pexels_api_key": "PEXELS_API_KEY",
        "pixabay_api_key": "PIXABAY_API_KEY", "stock_provider": "TRENDFORGE_STOCK_PROVIDER",
        "speech_model": "TRENDFORGE_SPEECH_MODEL",
    }

    def __init__(self, directory=DATA):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        keyfile = self.directory / "config.key"
        if not keyfile.exists():
            fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Fernet.generate_key())
        self.cipher = Fernet(keyfile.read_bytes())
        self.path = self.directory / "settings.enc"
        self.values = dict(self.defaults)
        if self.path.exists():
            self.values.update(json.loads(self.cipher.decrypt(self.path.read_bytes())))
        if not self.values["service_token"]:
            self.update({"service_token": secrets.token_urlsafe(40)})

    def get(self, key, default=None):
        with self.lock:
            name = self.env_names.get(key)
            if name and name in os.environ:
                return os.environ[name].strip()
            return self.values.get(key, default)

    def source(self, key):
        if self.env_names.get(key) in os.environ:
            return "environment"
        return "saved" if self.values.get(key) != self.defaults.get(key) else "default"

    def update(self, values):
        with self.lock:
            self.values.update(values)
            temp = self.path.with_suffix(".tmp")
            temp.write_bytes(self.cipher.encrypt(json.dumps(self.values).encode()))
            try:
                os.chmod(temp, 0o600)
            except OSError:
                pass
            temp.replace(self.path)

    def public(self):
        return {
            "ai_engine": self.get("ai_engine"),
            "ai_connected": self.get("ai_engine") == "openai_compatible" and bool(self.get("ai_base_url") and self.get("ai_model")),
            "ai_key_configured": bool(self.get("ai_api_key")),
            "youtube_configured": bool(self.get("youtube_api_key")),
            "pexels_configured": bool(self.get("pexels_api_key")),
            "pixabay_configured": bool(self.get("pixabay_api_key")),
            "stock_provider": self.get("stock_provider"),
            "stock_configured": bool(self.get(self.get("stock_provider") + "_api_key")),
            "speech_model": self.get("speech_model"),
            "storage_path": str(self.directory),
            "configuration_sources": {key: self.source(key) for key in self.env_names},
        }

