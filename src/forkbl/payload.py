"""Decode the accessclient URI returned by shterm."""

from __future__ import annotations

import base64
import json
import zlib
from urllib.parse import unquote


PREFIX = "accessclient://"


def decode_access_url(url: str) -> dict:
    if not url.startswith(PREFIX):
        raise ValueError("unsupported launcher URL (expected accessclient://)")
    encoded = unquote(url[len(PREFIX) :])
    try:
        decoded = base64.b64decode(encoded, validate=True)
        payload = zlib.decompress(decoded)
        result = json.loads(payload)
    except (ValueError, zlib.error, json.JSONDecodeError) as exc:
        raise ValueError("invalid accessclient payload") from exc
    if not isinstance(result, dict):
        raise ValueError("accessclient payload is not an object")
    return result
