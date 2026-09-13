"""Launch the system OpenSSH client with a ForkBL askpass helper."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pexpect


def run_ssh(
    payload: dict,
    extra_options: list[str] | None = None,
    remote_command: list[str] | None = None,
    verbose: int = 0,
) -> int:
    """Run an interactive SSH shell or a command inside the bastion shell."""
    required = ("un", "hn", "pn", "pw")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise RuntimeError(f"access payload missing: {', '.join(missing)}")

    # The access payload's pw value is the literal SSH password. Its Base64
    # decoding is only a diagnostic representation and must not be passed to
    # the bastion instead.
    password = str(payload["pw"])
    askpass = _askpass_path()
    print(f"Connecting to {payload['un']}@{payload['hn']}:{payload['pn']} ...", flush=True)
    command = _ssh_command(
        payload,
        extra_options=extra_options,
        verbose=verbose,
        allocate_tty=bool(remote_command),
    )
    env = _ssh_environment(password, askpass)

    if remote_command:
        return _run_shell_command(command, env, remote_command)

    process = subprocess.Popen(command, env=env)
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        return 130


def _ssh_command(
    payload: dict,
    *,
    extra_options: list[str] | None,
    verbose: int,
    allocate_tty: bool,
) -> list[str]:
    command = ["ssh"]
    if verbose:
        command.append(f"-{'v' * min(verbose, 3)}")
    if allocate_tty:
        command.append("-tt")
    command.extend(
        [
            "-p",
            str(payload["pn"]),
            "-o",
            "PreferredAuthentications=keyboard-interactive,password",
            "-o",
            "PasswordAuthentication=yes",
            "-o",
            "PubkeyAuthentication=no",
            "-o",
            "KbdInteractiveAuthentication=yes",
            "-o",
            "NumberOfPasswordPrompts=1",
            "-o",
            "ConnectTimeout=20",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={_null_device()}",
            "-o",
            "HostKeyAlgorithms=+ssh-rsa",
            "-o",
            "KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha1",
            "-o",
            "Ciphers=+aes128-cbc,aes192-cbc,aes256-cbc,3des-cbc",
            "-o",
            "MACs=+hmac-sha1,hmac-sha1-96",
        ]
    )
    command.extend(extra_options or [])
    command.append(f"{payload['un']}@{payload['hn']}")
    return command


def _ssh_environment(password: str, askpass: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "FORKBL_PASSWORD": password,
            "SSH_ASKPASS": str(askpass),
            # OpenSSH requires a non-empty DISPLAY before it considers askpass.
            "DISPLAY": env.get("DISPLAY") or "forkbl",
            "SSH_ASKPASS_REQUIRE": "force",
        }
    )
    # Do not let an agent socket change the requested password-only flow.
    env.pop("SSH_AUTH_SOCK", None)
    return env


def _run_shell_command(command: list[str], env: dict[str, str], remote_command: list[str]) -> int:
    """Run a command in the bastion shell while preserving full TTY behavior."""
    child = pexpect.spawn(command[0], command[1:], env=env, encoding="utf-8", codec_errors="replace")
    prompt = re.compile(r"(?m)^[^\r\n]*[#$%>] ?$")
    marker = re.compile(r"__FORKBL_RC:(\d+)__")
    marker_bytes = re.compile(rb"__FORKBL_RC:(\d+)__")
    try:
        child.expect(prompt, timeout=30)
        _write_text(child.before + child.after)

        command_text = shlex.join(remote_command)
        # The gateway ignores SSH's exec request and always starts a shell.
        # Run the requested command there, then propagate its status by
        # exiting the forced shell. Keeping the PTY attached also supports
        # full-screen programs such as vim, less, and top.
        child.sendline(f"{command_text}; _forkbl_rc=$?; printf '\\n__FORKBL_RC:%s__\\n' \"$_forkbl_rc\"; exit $_forkbl_rc")
        if sys.stdin.isatty():
            result = {"code": None, "pending": b""}

            def output_filter(data: bytes) -> bytes:
                data = result["pending"] + data
                found = marker_bytes.search(data)
                if found:
                    result["code"] = int(found.group(1))
                    result["pending"] = b""
                    start, end = found.span()
                    return data[:start] + data[end:]
                prefix = b"__FORKBL_RC:"
                for length in range(min(len(prefix) - 1, len(data)), 0, -1):
                    if data.endswith(prefix[:length]):
                        result["pending"] = data[-length:]
                        return data[:-length]
                return data

            child.interact(escape_character=None, output_filter=output_filter)
            if result["pending"]:
                _write_text(result["pending"].decode("utf-8", "replace"))
            return_code = result["code"]
        else:
            # Piped callers have no local TTY for pexpect.interact(); the
            # child still owns a PTY and will exit after the command.
            child.expect(pexpect.EOF, timeout=300)
            output = child.before
            found = marker.search(output)
            if found:
                start, end = found.span()
                _write_text(output[:start] + output[end:])
                return_code = int(found.group(1))
            else:
                _write_text(output)
                return_code = child.exitstatus
        if return_code is None:
            return_code = 1
        return return_code
    except KeyboardInterrupt:
        child.terminate(force=True)
        return 130
    except (pexpect.EOF, pexpect.TIMEOUT) as exc:
        raise RuntimeError("remote shell did not produce the expected prompt") from exc
    finally:
        if child.isalive():
            child.terminate(force=True)


def _write_text(value: str) -> None:
    sys.stdout.write(value)
    sys.stdout.flush()


def _askpass_path() -> Path:
    """Find the console script installed alongside the active Python."""
    found = shutil.which("forkbl-askpass")
    if found:
        return Path(found)
    executable_dir = Path(sys.executable).parent
    candidates = [executable_dir / "forkbl-askpass"]
    if os.name == "nt":
        candidates.extend(
            [executable_dir / "forkbl-askpass.exe", executable_dir / "forkbl-askpass.cmd"]
        )
    for sibling in candidates:
        if sibling.is_file() and (os.name == "nt" or os.access(sibling, os.X_OK)):
            return sibling
    raise RuntimeError("forkbl-askpass helper is not installed; run `uv sync`")


def _null_device() -> str:
    """Return the native null device name used by OpenSSH on this OS."""
    return "NUL" if os.name == "nt" else "/dev/null"
