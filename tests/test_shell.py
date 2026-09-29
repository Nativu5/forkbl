import shlex

import pytest

from forkbl._shell import CommandOutput


@pytest.mark.parametrize("code", [0, 1, 23, 130, 255])
def test_exit_status_survives_every_read_boundary(code):
    template = CommandOutput()
    marker = template.prefix + str(code).encode() + b"__"
    data = b"before\r\n" + marker + b"\r\nafter"
    for boundary in range(len(data) + 1):
        output = CommandOutput()
        output.prefix = template.prefix
        clean = output.feed(data[:boundary]) + output.feed(data[boundary:]) + output.finish()
        assert clean == b"before\r\n\r\nafter"
        assert output.return_code == code


def test_echoed_command_does_not_set_status():
    output = CommandOutput()
    args = ["printf", "%s", "a b", "don't expand $HOME; x", "中文"]
    command = output.command_line(args)
    assert shlex.split(command.split("; _forkbl_rc=", 1)[0]) == args
    echoed = command.encode()
    assert output.feed(echoed) + output.finish() == echoed
    assert output.return_code is None


@pytest.mark.parametrize("suffix", [b"", b"2", b"23_", b"oops__", b"999__", b"1234__"])
def test_incomplete_or_invalid_status_is_preserved(suffix):
    output = CommandOutput()
    data = b"message " + output.prefix + suffix
    assert output.feed(data) + output.finish() == data
    assert output.return_code is None


def test_unrelated_marker_is_preserved():
    output = CommandOutput()
    data = b"__FORKBL_RC:123__ __FORKBL_RC_other:1__"
    assert output.feed(data) + output.finish() == data
    assert output.return_code is None
