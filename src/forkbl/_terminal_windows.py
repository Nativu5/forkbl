"""Windows ConPTY implementation; this module is never imported on Unix."""

from __future__ import annotations

from contextlib import contextmanager
import codecs
import ctypes
from ctypes import wintypes
import msvcrt
import queue
import sys
import threading
from collections.abc import Callable

from winpty import Backend, PtyProcess

from ._shell import TextOutput, terminal_size


@contextmanager
def _console_mode():
    """Pass VT keys and Ctrl-C to the child, restoring the caller's console."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetConsoleMode.restype = wintypes.BOOL
    kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.SetConsoleMode.restype = wintypes.BOOL
    saved = []
    try:
        for stream, is_input in ((sys.stdin, True), (sys.stdout, False)):
            if not stream.isatty():
                continue
            handle = msvcrt.get_osfhandle(stream.fileno())
            mode = wintypes.DWORD()
            if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                raise ctypes.WinError(ctypes.get_last_error())
            # Disable processed, line, echo and Quick Edit input; enable VT.
            new_mode = (mode.value & ~(0x1 | 0x2 | 0x4 | 0x40)) | 0x80 | 0x200 if is_input else mode.value | 0x4
            if not kernel.SetConsoleMode(handle, new_mode):
                raise ctypes.WinError(ctypes.get_last_error())
            saved.append((handle, mode.value))
        yield
    finally:
        for handle, mode in reversed(saved):
            kernel.SetConsoleMode(handle, mode)


@contextmanager
def _console_input():
    """Read raw VT input, including Ctrl-C, without leaving a blocked reader."""
    # msvcrt.getwch() cannot read Ctrl-C. ReadConsoleW can when processed
    # input is disabled; CancelSynchronousIo releases it when SSH exits.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.ReadConsoleW.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel.ReadConsoleW.restype = wintypes.BOOL
    kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenThread.restype = wintypes.HANDLE
    kernel.CancelSynchronousIo.argtypes = [wintypes.HANDLE]
    kernel.CancelSynchronousIo.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = msvcrt.get_osfhandle(sys.stdin.fileno())
    events: queue.Queue[str | Exception] = queue.Queue()
    stopped = threading.Event()

    def read():
        decoder = codecs.getincrementaldecoder("utf-16-le")("replace")
        buffer = ctypes.create_unicode_buffer(1024)
        count = wintypes.DWORD()
        while not stopped.is_set():
            if not kernel.ReadConsoleW(handle, buffer, len(buffer), ctypes.byref(count), None):
                if not stopped.is_set():
                    events.put(ctypes.WinError(ctypes.get_last_error()))
                return
            data = ctypes.string_at(ctypes.addressof(buffer), count.value * 2)
            events.put(decoder.decode(data))

    reader = threading.Thread(target=read, name="forkbl-console-input", daemon=True)
    reader.start()
    try:
        yield events
    finally:
        stopped.set()
        thread_handle = kernel.OpenThread(0x1, False, reader.native_id)
        if thread_handle:
            try:
                # A cancellation can race with the next read; retry until the
                # reader has exited before restoring the caller's input mode.
                while reader.is_alive():
                    kernel.CancelSynchronousIo(thread_handle)
                    reader.join(timeout=0.05)
            finally:
                kernel.CloseHandle(thread_handle)


class WindowsTerminal:
    def __init__(self, command: list[str], env: dict[str, str], size: tuple[int, int]):
        # ConPTY requires Windows 10 1809 or newer and preserves VT sequences.
        self.child = PtyProcess.spawn(command, env=env, dimensions=size, backend=Backend.ConPTY)
        self.size = size
        self.exitstatus = 1
        self.closed = False
        self.events: queue.Queue[bytes | Exception] = queue.Queue(maxsize=64)
        self.stopped = threading.Event()
        self.reader = threading.Thread(target=self._read_output, name="forkbl-pty-output", daemon=True)
        self.reader.start()

    def _read_output(self) -> None:
        while not self.stopped.is_set():
            try:
                event = self.child.read(4096).encode("utf-8")
            except Exception as exc:
                event = exc
            while not self.stopped.is_set():
                try:
                    self.events.put(event, timeout=0.1)
                    break
                except queue.Full:
                    continue
            if isinstance(event, Exception):
                return

    def read(self, timeout: float) -> bytes:
        try:
            event = self.events.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError from exc
        if isinstance(event, Exception):
            raise event
        return event

    def sendline(self, text: str) -> None:
        self.child.write(text + "\r")

    def interact(self, output_filter: Callable[[bytes], bytes]) -> None:
        output = TextOutput()
        input_open = True
        with _console_mode(), _console_input() as keys:
            while True:
                try:
                    data = self.read(0.02)
                except TimeoutError:
                    pass
                except EOFError:
                    break
                else:
                    output.write(output_filter(data))
                while input_open and not keys.empty():
                    char = keys.get_nowait()
                    if isinstance(char, Exception):
                        raise char
                    try:
                        self.child.write(char)
                    except EOFError:
                        # SSH may exit while its last output is still queued.
                        # Stop forwarding keys, but drain output through EOF.
                        input_open = False
                        break
                size = terminal_size()
                if input_open and size != self.size:
                    self.child.setwinsize(*size)
                    self.size = size
        output.write(b"", final=True)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.stopped.set()
        try:
            self.child.close(force=True)
            code = self.child.exitstatus
            if code is not None:
                self.exitstatus = code
        finally:
            self.reader.join(timeout=1)
