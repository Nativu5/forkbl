import pytest

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


def test_server_change_rejected_before_sending_cookies(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_session("https://original.example/shterm/", {"SESSION": "test-session"})

    def unexpected_request(*args, **kwargs):
        pytest.fail("server mismatch must be rejected before making any HTTP request")

    monkeypatch.setattr("requests.Session.request", unexpected_request)
    with pytest.raises(RuntimeError, match="server URL changed"):
        ShtermClient.from_saved(base_url="https://other.example/shterm/")
    assert load_session() == (
        "https://original.example/shterm/", {"SESSION": "test-session"}
    )


def test_saved_server_used_without_override(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_session("https://saved.example/shterm/", {"SESSION": "test-session"})
    client = ShtermClient.from_saved()
    assert client.base_url == "https://saved.example/shterm/"
    assert client.http.cookies.get_dict() == {"SESSION": "test-session"}
    assert ShtermClient.from_saved(base_url="https://saved.example/shterm").base_url == client.base_url
