"""Resolve the shterm server address from CLI and environment settings."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import dotenv_values


def normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ValueError("server URL must be an HTTP(S) base URL without credentials, query, or fragment")
    # Validate the port before a request is attempted.
    _ = parts.port
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/") + "/", "", ""))


def configured_url(cli_url: str | None = None) -> str | None:
    value = cli_url
    if value is None:
        value = os.environ.get("FORKBL_URL")
    if value is None:
        value = dotenv_values(Path.cwd() / ".env").get("FORKBL_URL")
    return normalize_url(value) if value is not None else None
