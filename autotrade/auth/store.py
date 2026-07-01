"""JSON-file-based user store — thread-safe persistence."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# User data directory — relative to project root (same level as data/)
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_USERS_FILE = _DATA_DIR / "users.json"


class UserRecord:
    """Immutable-ish user record."""
    __slots__ = ("id", "username", "password_hash", "created_at")

    def __init__(self, id: str, username: str, password_hash: str, created_at: str):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.created_at = created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UserRecord":
        return cls(
            id=d["id"],
            username=d["username"],
            password_hash=d["password_hash"],
            created_at=d.get("created_at", ""),
        )


class UserStore:
    """Thread-safe JSON file user store."""

    def __init__(self, filepath: Optional[Path] = None):
        self._filepath = filepath or _USERS_FILE
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Create the data directory and users file if they don't exist."""
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        if not self._filepath.exists():
            self._write({})

    def _read(self) -> dict[str, dict]:
        """Read all users from disk. Caller must hold lock."""
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write(self, data: dict[str, dict]) -> None:
        """Write all users to disk. Caller must hold lock."""
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_by_username(self, username: str) -> Optional[UserRecord]:
        """Find a user by username (case-insensitive)."""
        username_lower = username.lower()
        with self._lock:
            data = self._read()
            for uid, d in data.items():
                if d.get("username", "").lower() == username_lower:
                    return UserRecord.from_dict(d)
            return None

    def get_by_id(self, user_id: str) -> Optional[UserRecord]:
        """Find a user by ID."""
        with self._lock:
            data = self._read()
            d = data.get(user_id)
            if d:
                return UserRecord.from_dict(d)
            return None

    def create_user(self, username: str, password_hash: str) -> UserRecord:
        """Create a new user. Raises ValueError if username already exists."""
        username = username.strip()
        if not username:
            raise ValueError("用户名不能为空")

        with self._lock:
            data = self._read()

            # Check for duplicate (case-insensitive)
            username_lower = username.lower()
            for d in data.values():
                if d.get("username", "").lower() == username_lower:
                    raise ValueError("用户名已存在")

            user_id = uuid.uuid4().hex[:16]
            created_at = datetime.now(timezone.utc).isoformat()
            record = UserRecord(
                id=user_id,
                username=username,
                password_hash=password_hash,
                created_at=created_at,
            )
            data[user_id] = record.to_dict()
            self._write(data)
            return record


# Module-level singleton
_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    """Get or create the module-level UserStore singleton."""
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store
