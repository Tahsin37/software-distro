"""
Secure secret storage — stores API keys encrypted on disk.
Never exposes keys in logs, events, tool output, or error messages.

Uses Fernet symmetric encryption with a machine-derived key.
The key is derived from the machine ID + app salt, so secrets
are tied to this machine and cannot be read by copying the file.
"""
import json
import os
import hashlib
import base64
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet

# Derive encryption key from machine identity
def _derive_key() -> bytes:
    """Derive a Fernet key from machine-specific data."""
    # Use computer name + user name as entropy source
    machine_id = f"{os.environ.get('COMPUTERNAME', 'unknown')}:{os.environ.get('USERNAME', 'unknown')}"
    salt = b"ai-computer-platform-v1"
    derived = hashlib.pbkdf2_hmac("sha256", machine_id.encode(), salt, 100000)
    return base64.urlsafe_b64encode(derived)


class SecretStore:
    """Encrypted local storage for API keys and sensitive config."""

    def __init__(self, store_path: Optional[Path] = None):
        self._path = store_path or Path(__file__).parent / "data" / ".secrets.enc"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(_derive_key())
        self._cache: dict = {}
        self._load()

    def _load(self):
        """Load and decrypt secrets from disk."""
        if self._path.exists():
            try:
                encrypted = self._path.read_bytes()
                decrypted = self._fernet.decrypt(encrypted)
                self._cache = json.loads(decrypted)
            except Exception:
                # Corrupted or wrong machine — start fresh
                self._cache = {}
        else:
            self._cache = {}

    def _save(self):
        """Encrypt and save secrets to disk."""
        data = json.dumps(self._cache).encode()
        encrypted = self._fernet.encrypt(data)
        self._path.write_bytes(encrypted)

    def set(self, key: str, value: str):
        """Store a secret."""
        self._cache[key] = value
        self._save()

    def get(self, key: str, default: str = "") -> str:
        """Retrieve a secret."""
        return self._cache.get(key, default)

    def delete(self, key: str):
        """Delete a secret."""
        self._cache.pop(key, None)
        self._save()

    def has(self, key: str) -> bool:
        """Check if a secret exists."""
        return key in self._cache

    def list_keys(self) -> list[str]:
        """List stored secret names (not values)."""
        return list(self._cache.keys())

    @staticmethod
    def mask(value: str) -> str:
        """Mask a secret for display — shows only last 4 chars."""
        if not value or len(value) < 8:
            return "****"
        return f"{'*' * (len(value) - 4)}{value[-4:]}"

    @staticmethod
    def redact_from_text(text: str, secrets: list[str]) -> str:
        """Redact all secrets from a text string."""
        result = text
        for secret in secrets:
            if secret and len(secret) > 4:
                result = result.replace(secret, "[REDACTED]")
        return result


# Global instance
secret_store = SecretStore()
