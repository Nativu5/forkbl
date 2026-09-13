"""Minimal SSH_ASKPASS helper used by the system OpenSSH client."""

from __future__ import annotations

import os
import sys


def main() -> int:
    """Write the one-time password supplied by ForkBL to stdout."""
    password = os.environ.get("FORKBL_PASSWORD")
    if password is None:
        return 1
    sys.stdout.write(password + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
