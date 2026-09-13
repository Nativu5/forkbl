"""Small terminal presentation helpers shared by the CLI."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table


console = Console()
error_console = Console(stderr=True)


def print_targets(rows: list[dict]) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Address")
    table.add_column("System")
    for row in rows:
        device = row.get("dev", {})
        table.add_row(
            str(device.get("id", row.get("id", "-"))),
            str(device.get("name", "-")),
            str(device.get("ip", "-")),
            str(device.get("sysType", {}).get("name", "-")),
        )
    console.print(table)
