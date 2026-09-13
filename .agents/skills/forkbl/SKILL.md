---
name: forkbl
description: Use the ForkBL CLI to authenticate to the shterm bastion, inspect available targets, and open or run commands through SSH.
---

# ForkBL

Use ForkBL when the user asks to access a managed bastion target through this repository's shterm integration.

- Authenticate first with `forkbl login`; use `forkbl targets` to resolve a device ID.
- Open an interactive session with `forkbl ssh DEVICE_ID`.
- Run a remote command with `forkbl ssh DEVICE_ID -- COMMAND [ARG ...]`. The command runs inside the bastion's allocated PTY, so TUI programs are supported.
- Each `forkbl ssh` invocation requests a fresh access credential from the server. Do not add or assume SSH ControlMaster reuse.
- Use `--verbose`/`-v` only for diagnosis. It prints the complete temporary `accessclient://` URL; treat that output as sensitive and do not paste it into messages or logs.
- Preserve the user's SSH session and command exactly. Do not run remote commands with side effects unless the user explicitly requests them.
- If authentication expires, ask the user to run `forkbl login` again.
