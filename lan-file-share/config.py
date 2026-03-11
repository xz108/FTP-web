from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


LAN_HOST = os.getenv("LAN_HOST", "0.0.0.0")
LAN_PORT = int(os.getenv("LAN_PORT", "8000"))
ROOT_DIR = Path(os.getenv("ROOT_DIR", str(BASE_DIR / "shared"))).resolve()

AUTH_ENABLED = _env_bool("AUTH_ENABLED", True)
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")

SESSION_COOKIE = os.getenv("SESSION_COOKIE", "lanfs_session")

MAX_TEXT_PREVIEW_KB = int(os.getenv("MAX_TEXT_PREVIEW_KB", "200"))
