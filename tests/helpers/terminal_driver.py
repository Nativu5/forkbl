"""Run the command layer in an outer terminal and check console restoration."""

import ctypes
import os
from pathlib import Path
import sys
import threading

from forkbl._shell import run_shell_command


def console_state():
    if os.name != "nt":
        import termios
        return termios.tcgetattr(0)
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    modes = []
    for descriptor in (0, 1):
        mode = wintypes.DWORD()
        assert kernel.GetConsoleMode(msvcrt.get_osfhandle(descriptor), ctypes.byref(mode))
        modes.append(mode.value)
    return modes


before = console_state()
mode = sys.argv[1] if len(sys.argv) > 1 else "interactive"
code = run_shell_command(
    [sys.executable, "-u", str(Path(__file__).with_name("terminal_child.py")), mode],
    os.environ.copy(), ["23"], prompt_timeout=5, command_timeout=10,
)
assert console_state() == before, "console modes were not restored"
assert not any(thread.name.startswith("forkbl-") for thread in threading.enumerate()), "terminal reader leaked"
print("CONSOLE_RESTORED", flush=True)
raise SystemExit(code)
