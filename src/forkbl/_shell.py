"""Shared command protocol for the platform-specific SSH terminals."""

from __future__ import annotations

import codecs
import os
import re
import secrets
import shlex
import sys
import time


_ANSI = re.compile(rb"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)")
_PROMPT = re.compile(rb"(?m)^[^\r\n]*[#$%>] ?$")


def terminal_size() -> tuple[int, int]:
    """Return (rows, columns), including changes to the current console."""
    for stream in (sys.stdout, sys.stdin):
        try:
            size = os.get_terminal_size(stream.fileno())
            return size.lines, size.columns
        except (AttributeError, OSError, ValueError):
            pass
    return 24, 80


class CommandOutput:
    """Remove only this invocation's status marker, across arbitrary reads."""

    def __init__(self) -> None:
        self.prefix = f"__FORKBL_RC_{secrets.token_hex(8)}:".encode()
        self.pending = b""
        self.return_code: int | None = None

    def command_line(self, command: list[str]) -> str:
        # The gateway always opens a shell, ignoring SSH exec requests.
        return (
            f"{shlex.join(command)}; _forkbl_rc=$?; "
            f"printf '\\n{self.prefix.decode()}%s__\\n' \"$_forkbl_rc\"; exit $_forkbl_rc"
        )

    def feed(self, data: bytes) -> bytes:
        data = self.pending + data
        self.pending = b""
        output = bytearray()
        while data:
            start = data.find(self.prefix)
            if start < 0:
                for length in range(min(len(self.prefix) - 1, len(data)), 0, -1):
                    if data.endswith(self.prefix[:length]):
                        self.pending = data[-length:]
                        return bytes(output) + data[:-length]
                return bytes(output) + data
            output.extend(data[:start])
            data = data[start:]
            suffix = data[len(self.prefix):]
            match = re.match(rb"([0-9]{1,3})__", suffix)
            if match and int(match[1]) <= 255:
                self.return_code = int(match[1])
                data = data[len(self.prefix) + match.end():]
            elif re.fullmatch(rb"[0-9]{0,3}_?", suffix):
                self.pending = data
                break
            else:
                # The echoed printf command contains %s, not a status.
                output.extend(data[:1])
                data = data[1:]
        return bytes(output)

    def finish(self) -> bytes:
        pending, self.pending = self.pending, b""
        return pending


class TextOutput:
    def __init__(self) -> None:
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def write(self, data: bytes, *, final: bool = False) -> None:
        sys.stdout.write(self.decoder.decode(data, final=final))
        sys.stdout.flush()


def run_shell_command(
    command: list[str],
    env: dict[str, str],
    remote_command: list[str],
    *,
    prompt_timeout: float = 30,
    command_timeout: float = 300,
) -> int:
    # Import only the backend installed for this platform.
    if sys.platform == "win32":
        from ._terminal_windows import WindowsTerminal as Terminal
    else:
        from ._terminal_posix import PosixTerminal as Terminal

    terminal = Terminal(command, env, terminal_size())
    output = TextOutput()
    status = CommandOutput()
    try:
        deadline = time.monotonic() + prompt_timeout
        prompt_buffer = b""
        while True:
            try:
                data = terminal.read(max(0, deadline - time.monotonic()))
            except (EOFError, TimeoutError) as exc:
                raise RuntimeError("remote shell did not produce the expected prompt") from exc
            output.write(data)
            prompt_buffer = (prompt_buffer + data)[-8192:]
            if _PROMPT.search(_ANSI.sub(b"", prompt_buffer)):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("remote shell did not produce the expected prompt")

        terminal.sendline(status.command_line(remote_command))
        if sys.stdin.isatty():
            terminal.interact(status.feed)
        else:
            deadline = time.monotonic() + command_timeout
            while True:
                try:
                    data = terminal.read(max(0, deadline - time.monotonic()))
                except EOFError:
                    break
                except TimeoutError as exc:
                    raise RuntimeError("remote command timed out") from exc
                output.write(status.feed(data))
                if time.monotonic() >= deadline:
                    raise RuntimeError("remote command timed out")
        output.write(status.finish(), final=True)
        terminal.close()
        return status.return_code if status.return_code is not None else terminal.exitstatus
    except KeyboardInterrupt:
        return 130
    finally:
        terminal.close()
