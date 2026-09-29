"""Deterministic terminal peer: no network, credentials or remote commands."""

import json
import os
import re
import shlex
import sys
import time


mode = sys.argv[1]
if mode == "no-prompt":
    print("not a shell", flush=True)
    raise SystemExit(19)
if mode == "hang-before-prompt":
    time.sleep(30)
    raise SystemExit()

print("\x1b[32mlocal-fixture$ \x1b[0m", end="", flush=True)
line = sys.stdin.readline()
if mode == "disconnect":
    raise SystemExit(19)
if mode == "hang-after-prompt":
    time.sleep(30)
    raise SystemExit()

prefix = re.search(r"(__FORKBL_RC_[0-9a-f]+:)%s__", line)[1]
args = shlex.split(line.split("; _forkbl_rc=", 1)[0])
print(json.dumps({"args": args, "stdin_tty": sys.stdin.isatty(), "stdout_tty": sys.stdout.isatty()}, ensure_ascii=False), flush=True)

if mode == "interactive":
    if os.name == "nt":
        from forkbl._terminal_windows import _console_mode

        with _console_mode():
            print("\x1b[?1049h\x1b[2J\x1b[HKEYS_READY", flush=True)
            chars = []
            while True:
                char = sys.stdin.read(1)
                chars.append(char)
                if char == "\x03":
                    break
    else:
        import termios
        import tty

        original = termios.tcgetattr(0)
        try:
            tty.setraw(0)
            print("\x1b[?1049h\x1b[2J\x1b[HKEYS_READY", flush=True)
            chars = []
            while True:
                char = os.read(0, 1).decode()
                chars.append(char)
                if char == "\x03":
                    break
        finally:
            termios.tcsetattr(0, termios.TCSANOW, original)
    size = os.get_terminal_size()
    print("\x1b[?1049l", end="", flush=True)
    print("INPUT=" + json.dumps("".join(chars)), flush=True)
    print(f"SIZE={size.lines}x{size.columns}", flush=True)

print("COMMAND_OUTPUT_中文", flush=True)
marker = prefix + str(int(args[0])) + "__"
# Force the status, its digits, and its terminator into separate PTY reads.
for chunk in (marker[:9], marker[9:-3], marker[-3:-1], marker[-1:] + "\n"):
    sys.stdout.write(chunk)
    sys.stdout.flush()
    time.sleep(0.04)
raise SystemExit(0)  # The remote command's status must take precedence.
