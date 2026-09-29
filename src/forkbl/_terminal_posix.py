"""Unix PTY implementation; this module is never imported on Windows."""

from __future__ import annotations

import signal
from collections.abc import Callable

import pexpect

from ._shell import terminal_size


class PosixTerminal:
    def __init__(self, command: list[str], env: dict[str, str], size: tuple[int, int]):
        self.child = pexpect.spawn(command[0], command[1:], env=env, dimensions=size)
        self.closed = False
        self.exitstatus = 1

    def read(self, timeout: float) -> bytes:
        try:
            return self.child.read_nonblocking(4096, timeout=timeout)
        except pexpect.EOF as exc:
            raise EOFError from exc
        except pexpect.TIMEOUT as exc:
            raise TimeoutError from exc

    def sendline(self, text: str) -> None:
        self.child.sendline(text.encode("utf-8"))

    def interact(self, output_filter: Callable[[bytes], bytes]) -> None:
        def resize(*_):
            self.child.setwinsize(*terminal_size())

        previous = signal.signal(signal.SIGWINCH, resize)
        try:
            resize()
            self.child.interact(escape_character=None, output_filter=output_filter)
        finally:
            signal.signal(signal.SIGWINCH, previous)

    def close(self) -> None:
        if not self.closed:
            self.child.close(force=True)
            self.closed = True
            if self.child.exitstatus is not None:
                self.exitstatus = self.child.exitstatus
            elif self.child.signalstatus is not None:
                self.exitstatus = 128 + self.child.signalstatus
