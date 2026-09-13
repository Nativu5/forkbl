"""Local persistence for an authenticated shterm HTTP session."""

from __future__ import annotations

import json
import os
from pathlib import Path


def session_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "forkbl" / "session.json"


def save_session(base_url: str, cookies: dict[str, str]) -> None:
    path = session_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps({"base_url": base_url, "cookies": cookies}, indent=2) + "\n")
    path.chmod(0o600)


def load_session() -> tuple[str, dict[str, str]]:
    path = session_path()
    try:
        data = json.loads(path.read_text())
        return str(data["base_url"]), {str(k): str(v) for k, v in data["cookies"].items()}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("not logged in; run 'forkbl login' first") from exc


def clear_session() -> None:
    try:
        session_path().unlink()
    except FileNotFoundError:
        pass
