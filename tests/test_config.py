import pytest

from forkbl.__main__ import _parser
from forkbl.client import ShtermClient
from forkbl.config import configured_url
from forkbl.session import load_session, save_session


def test_url_precedence(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FORKBL_URL", raising=False)
    assert configured_url() is None

    (tmp_path / ".env").write_text('FORKBL_URL="https://file.example/shterm"\n')
    assert configured_url() == "https://file.example/shterm/"

    monkeypatch.setenv("FORKBL_URL", "https://env.example/shterm/")
    assert configured_url() == "https://env.example/shterm/"
    assert configured_url("https://cli.example/shterm") == "https://cli.example/shterm/"


def test_saved_server_used_without_override(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_session("https://saved.example/shterm/", {"SESSION": "test-session"})
    client = ShtermClient.from_saved()
    assert client.base_url == "https://saved.example/shterm/"
    assert client.http.cookies.get_dict() == {"SESSION": "test-session"}


def test_url_option_belongs_to_login(monkeypatch):
    args = _parser().parse_args(["login", "--url", "https://cli.example/shterm"])
    assert args.url == "https://cli.example/shterm"

    with pytest.raises(SystemExit):
        _parser().parse_args(["targets", "--url", "https://cli.example/shterm"])
    with pytest.raises(SystemExit):
        _parser().parse_args(["--url", "https://cli.example/shterm", "login"])
