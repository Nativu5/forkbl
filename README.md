# ForkBL

ForkBL is a terminal client for the PKU shterm bastion host. It logs in over
HTTPS, lists visible devices, requests an SSH access URL, and starts the
system OpenSSH client. The old Windows protocol-handler implementation is
no longer required.

## Requirements

- Python 3.11 or newer
- `uv`
- the system `ssh` command

Windows uses the built-in Win32-OpenSSH client when it is available. For the
interactive askpass flow, use OpenSSH 8.4 or newer so that
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

Set the shterm base URL using `FORKBL_URL`:

```sh
export FORKBL_URL=https://bastion.example.com/shterm/
forkbl login
```

Alternatively, copy `.env.example` to `.env` in the directory where you run
ForkBL and edit the URL. ForkBL reads that file without modifying the process
environment. The `.env` file is excluded from Git.

Precedence: `--url` > `FORKBL_URL` environment variable > `.env`. Pass `--url`
before the subcommand for a single invocation:

```sh
forkbl --url https://bastion.example.com/shterm/ login
```

There is no built-in server URL. The first `forkbl login` must receive one of
these settings. Subsequent commands use the server stored in the login
session. A different server requires `forkbl logout` before logging in again;
cookies from another server are never reused.
