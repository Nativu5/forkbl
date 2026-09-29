"""The same behavioral contract runs against the current platform's real PTY."""

import os
from contextlib import nullcontext
from pathlib import Path
import queue
import re
import sys
import threading
import time

import pytest

from forkbl._shell import CommandOutput, run_shell_command


HELPERS = Path(__file__).parent / "helpers"
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\].*?(?:\x07|\x1b\\)", re.S)


@pytest.fixture(params=[pytest.param("windows", marks=pytest.mark.windows), pytest.param("posix", marks=pytest.mark.posix)])
def native_backend(request):
    return request.param


@pytest.fixture
def terminal_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_peer(mode, env, args=None, **kwargs):
    return run_shell_command([sys.executable, "-u", str(HELPERS / "terminal_child.py"), mode], env, args or ["23"], **kwargs)


@pytest.mark.parametrize("code", [0, 23, 255])
def test_native_command_output_and_status(native_backend, terminal_env, capsys, code):
    args = [str(code), "a b", "don't expand $HOME; x", "中文"]
    assert run_peer("command", terminal_env, args) == code
    output = ANSI.sub("", capsys.readouterr().out)
    assert '"stdin_tty": true' in output and '"stdout_tty": true' in output
    assert "a b" in output and "don't expand $HOME; x" in output
    assert "COMMAND_OUTPUT_中文" in output
    # The echoed command contains %s; the actual numeric marker is removed.
    assert not re.search(r"__FORKBL_RC_[0-9a-f]+:\d+__", output)


def test_native_disconnect_status(native_backend, terminal_env):
    assert run_peer("disconnect", terminal_env) == 19


@pytest.mark.parametrize("mode", ["no-prompt", "hang-before-prompt"])
def test_native_missing_prompt(native_backend, terminal_env, mode):
    with pytest.raises(RuntimeError, match="expected prompt"):
        run_peer(mode, terminal_env, prompt_timeout=0.5)


def test_native_command_timeout(native_backend, terminal_env):
    with pytest.raises(RuntimeError, match="command timed out"):
        run_peer("hang-after-prompt", terminal_env, command_timeout=0.5)


@pytest.mark.parametrize("mode", ["interactive", "command"])
def test_native_interaction_resize_and_ctrl_c(native_backend, terminal_env, mode):
    command = [sys.executable, "-u", str(HELPERS / "terminal_driver.py"), mode]
    if native_backend == "windows":
        from winpty import PtyProcess
        child = PtyProcess.spawn(command, env=terminal_env, dimensions=(24, 100))
        read = lambda: child.read(4096)
        write = child.write
    else:
        import pexpect
        child = pexpect.spawn(command[0], command[1:], env=terminal_env, dimensions=(24, 100), encoding="utf-8")
        read = lambda: child.read_nonblocking(4096, timeout=15)
        write = child.send
    chunks = queue.Queue()

    def reader():
        try:
            while True:
                chunks.put(read())
        except Exception:
            chunks.put(None)

    worker = threading.Thread(target=reader, daemon=True)
    worker.start()
    output = ""

    def expect(text):
        nonlocal output
        deadline = time.monotonic() + 15
        while text not in ANSI.sub("", output):
            remaining = deadline - time.monotonic()
            assert remaining > 0, output
            try:
                chunk = chunks.get(timeout=remaining)
            except queue.Empty:
                pytest.fail(f"timed out waiting for {text!r}: {output!r}")
            assert chunk is not None, output
            output += chunk

    try:
        if mode == "interactive":
            expect("KEYS_READY")
            child.setwinsize(32, 110)
            # Allow the forwarding loop / SIGWINCH handler to propagate the resize.
            time.sleep(0.2)
            write("x\x1b[A\t\x03")
            expect("CONSOLE_RESTORED")
            expect("SIZE=32x110")
            assert 'INPUT="x\\u001b[A\\t\\u0003"' in ANSI.sub("", output)
        else:
            expect("CONSOLE_RESTORED")
        deadline = time.monotonic() + 10
        while child.isalive() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not child.isalive(), output
        if native_backend == "posix":
            child.close()
        assert child.exitstatus == 23, output
    finally:
        child.close(force=True)
        worker.join(timeout=1)


@pytest.mark.posix
def test_real_posix_shell(terminal_env, capsys):
    env = {**terminal_env, "PS1": "fixture$ "}
    code = run_shell_command(["/bin/sh", "-i"], env, ["sh", "-c", "printf 'hello 世界\\n'; exit 37"])
    assert code == 37
    assert "hello 世界" in capsys.readouterr().out


@pytest.mark.windows
def test_pending_key_after_child_exit_drains_output(terminal_env, monkeypatch, capsys):
    from forkbl import _terminal_windows

    status = CommandOutput()
    marker = status.prefix.decode() + "23__"
    terminal = _terminal_windows.WindowsTerminal(
        [sys.executable, "-u", "-c", "import sys; print('A' * 12000 + 'TAIL_OUTPUT_MUST_SURVIVE' + sys.argv[1])", marker],
        terminal_env, (24, 100),
    )
    try:
        terminal.reader.join(timeout=15)
        assert not terminal.reader.is_alive(), "fixture did not finish emitting output"
        deadline = time.monotonic() + 5
        while terminal.child.pty.isalive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not terminal.child.pty.isalive(), "fixture did not exit"
        keys = queue.Queue()
        keys.put("x")
        monkeypatch.setattr(_terminal_windows, "_console_mode", nullcontext)
        monkeypatch.setattr(_terminal_windows, "_console_input", lambda: nullcontext(keys))
        # An input failure must also prevent a resize of the finished PTY.
        monkeypatch.setattr(_terminal_windows, "terminal_size", lambda: (32, 110))
        monkeypatch.setattr(terminal.child, "setwinsize", lambda *_: pytest.fail("resized an exited child"))
        terminal.interact(status.feed)
        assert "TAIL_OUTPUT_MUST_SURVIVE" in ANSI.sub("", capsys.readouterr().out)
        assert status.return_code == 23
        assert terminal.events.empty()
    finally:
        terminal.close()
