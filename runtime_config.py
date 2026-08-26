from __future__ import annotations

import os
import secrets
from pathlib import Path

from config import BASE_DIR


def local_storage_secret() -> str:
    """Return a persistent local NiceGUI secret without asking the user for one."""
    location = BASE_DIR / "data" / ".nicegui_storage_secret"
    location.parent.mkdir(exist_ok=True)
    if location.exists():
        return location.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(48)
    location.write_text(secret, encoding="utf-8")
    try:
        os.chmod(location, 0o600)
    except OSError:
        pass
    return secret
