from __future__ import annotations

import argparse
import sys

from .client import ShtermClient
from .config import configured_url, normalize_url
from .session import clear_session, load_session
from .ssh import run_ssh
from .ui import console, error_console, print_targets


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forkbl", description="Terminal client for a shterm bastion host")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="show HTTP and SSH diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)
    login_parser = sub.add_parser("login")
    login_parser.add_argument("--url", help="shterm base URL (overrides FORKBL_URL and .env)")
    login_parser.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    targets_parser = sub.add_parser("targets")
    targets_parser.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    ssh_parser = sub.add_parser("ssh")
    ssh_parser.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    ssh_parser.add_argument("device_id", type=int)
    ssh_parser.add_argument(
        "remote_command",
        nargs=argparse.REMAINDER,
        metavar="-- COMMAND",
        help="optional command to run inside the remote PTY",
    )
    logout_parser = sub.add_parser("logout")
    logout_parser.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "login":
            base_url = configured_url(args.url)
            if base_url is None:
                raise RuntimeError("a server URL is required for login; use --url, FORKBL_URL, or .env")
            _ensure_single_server(base_url)
            ShtermClient(base_url, verbose=bool(args.verbose)).login_interactive()
            console.print("[green]Login successful.[/green]")
        elif args.command == "logout":
            try:
                ShtermClient.from_saved(verbose=bool(args.verbose)).logout()
            except RuntimeError as exc:
                if "not logged in" not in str(exc):
                    raise
            clear_session()
            console.print("Logged out.")
        else:
            client = ShtermClient.from_saved(verbose=bool(args.verbose))
            if args.command == "targets":
                print_targets(client.targets())
            elif args.command == "ssh":
                rows = [row for row in client.targets() if row.get("dev", {}).get("id", row.get("id")) == args.device_id]
                if not rows:
                    raise RuntimeError(f"device {args.device_id} not found")
                dev = rows[0].get("dev", {})
                account = client.default_account(args.device_id, dev)
                remote_command = args.remote_command
                if remote_command[:1] == ["--"]:
                    remote_command = remote_command[1:]
                return run_ssh(
                    client.access_payload(args.device_id, account),
                    remote_command=remote_command or None,
                    verbose=args.verbose,
                )
    except KeyboardInterrupt:
        error_console.print("Operation cancelled.")
        return 130
    except (RuntimeError, OSError, ValueError) as exc:
        error_console.print(f"forkbl: {exc}", style="red", markup=False)
        return 1
    except EOFError:
        error_console.print("Input ended.", style="red")
        return 1
    except Exception as exc:
        # Keep unexpected third-party errors concise for end users. Detailed
        # diagnostics remain available through --verbose where applicable.
        error_console.print(f"[red]forkbl:[/red] {exc}", markup=False)
        return 1
    return 0


def _ensure_single_server(base_url: str) -> None:
    try:
        saved_url, _ = load_session()
    except RuntimeError:
        return
    if normalize_url(base_url) != normalize_url(saved_url):
        raise RuntimeError("already logged in to another server; run 'forkbl logout' first")

if __name__ == "__main__":
    raise SystemExit(main())
