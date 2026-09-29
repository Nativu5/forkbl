# ForkBL

ForkBL is a terminal client for a shterm bastion host. It logs in over HTTPS,
lists visible devices, requests an SSH access URL, and starts the system
OpenSSH client. The old Windows protocol-handler implementation is no longer
required.

## Requirements

- Python 3.11 or newer
- `uv`
- the system `ssh` command

Windows uses the built-in Win32-OpenSSH client when it is available. For the
remote-command PTY, Windows requires Windows 10 version 1809 or newer (or
Windows Server 2019 or newer) and uses pywinpty with ConPTY. Linux and macOS
use pexpect with a Unix PTY. The matching dependency is installed automatically.

For the interactive askpass flow, use OpenSSH 8.4 or newer so that
`SSH_ASKPASS_REQUIRE=force` is supported; the OpenSSH 8.1 bundled with some
Windows 10 releases cannot force askpass while a console is attached.

```sh
uv sync
uv run forkbl --help
```

For a system-wide command that does not require `uv`, install the project with
`pipx`:

```sh
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install .
forkbl --help
```

To install a built wheel instead:

```sh
python3 -m pip install dist/forkbl-0.1.0-py3-none-any.whl
forkbl --help
```

`pipx` is preferred because it keeps ForkBL's dependencies isolated while
making both `forkbl` and `forkbl-askpass` available on `PATH`.

The CLI uses Rich for readable target tables and concise error messages.
Pressing `Ctrl-C` during login or another local operation cancels it cleanly
and returns status 130.

## Usage

```sh
uv run forkbl login
uv run forkbl targets
uv run forkbl ssh DEVICE_ID
uv run forkbl ssh DEVICE_ID -- COMMAND [ARG ...]
uv run forkbl logout
```

Add `--verbose` before the subcommand to print request status and pass `-v`
to the system SSH client. Repeat it for higher SSH verbosity (`-vv` or
`-vvv`):

```sh
uv run forkbl --verbose targets
uv run forkbl -vv ssh 2188
```

Diagnostic output does not print passwords, OTPs, or cookies as separate
fields. It intentionally prints the complete one-time `accessclient://` URL;
that URL may encode the temporary connection credential, so treat verbose
output as sensitive and short-lived.

`login` stores the authenticated cookie in
`~/.config/forkbl/session.json` with mode `0600`. Passwords and one-time
passwords remain in memory. `ssh` starts the system SSH command with
your terminal attached and supplies the access password through a
short-lived `SSH_ASKPASS` helper. The shell and all interaction therefore
remain native to `ssh`.

Pass a command after `--` for non-interactive execution. The bastion starts a
shell even when SSH receives a remote command, so ForkBL uses a PTY helper to
wait for that shell, send the command, and return its exit status:

```sh
uv run forkbl ssh 2188 -- ls -la /tmp
```

Command mode keeps the PTY attached, so TUI programs such as `vim`, `less`,
and `top` are supported as well.

Connections intentionally discard host keys (`/dev/null` on Unix and `NUL` on
Windows), accept the host key automatically, and enable legacy SSH algorithms
required by older bastion deployments.

Set the shterm base URL when logging in using `FORKBL_URL`:

```sh
export FORKBL_URL=https://bastion.example.com/shterm/
forkbl login
```

Alternatively, copy `.env.example` to `.env` in the directory where you run
ForkBL and edit the URL. ForkBL reads that file without modifying the process
environment. The `.env` file is excluded from Git.

For `forkbl login`, URL precedence is `--url` > `FORKBL_URL` environment
variable > `.env`. Pass `--url` to the `login` subcommand for a single
invocation:

```sh
forkbl login --url https://bastion.example.com/shterm/
```

There is no built-in server URL. The first `forkbl login` must receive one of
these settings. Subsequent commands use the server stored in the login
session; their URL and environment settings are ignored. A different server
requires `forkbl logout` before logging in again. Only one active session is
stored at a time.

## Tests

Run `uv sync --locked`, then `uv run --locked pytest -q -ra` on the target
operating system. Shared tests always run. Native terminal tests are marked
`windows` or `posix`; pytest skips the other platform automatically without
importing its backend. WSL uses the Unix implementation, not the Windows one.

To run only a platform's terminal checks:

```sh
uv run --locked pytest -m windows -q -ra  # native Windows
uv run --locked pytest -m posix -q -ra    # Linux/macOS, including WSL
```

The native tests launch real local PTYs and verify command quoting, Unicode
output, exit codes, timeouts, key forwarding, Ctrl-C, terminal resizing, and
console-mode restoration. They use synthetic local processes and do not log in
to a bastion. Keep separate Python environments when testing Windows and WSL;
do not share the same .venv directory between operating systems.
