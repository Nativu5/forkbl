from unittest.mock import Mock

import requests

from forkbl.client import ShtermClient


def response(status=200, text="", location=None, data=None):
    result = Mock()
    result.status_code = status
    result.text = text
    result.headers = {"Location": location} if location else {}
    result.ok = status < 400
    result.raise_for_status.return_value = None
    result.json.return_value = data
    return result


def test_two_stage_login_saves_session(monkeypatch):
    page = '<input name="_csrf" value="csrf"><script>var sessionId = "session";</script>'
    http = Mock()
    http.get.return_value = response(text=page)
    http.post.side_effect = [response(302, location="/shterm/login?tokenRequest"), response(302, location="/shterm/")]
    http.cookies = requests.cookies.RequestsCookieJar()
    http.cookies.set("SESSION", "test")
    saved = Mock()
    monkeypatch.setattr("forkbl.client.save_session", saved)

    ShtermClient("https://example.test/shterm/", http).login("alice", "password", "123456")

    assert http.post.call_count == 2
    assert dict(http.post.call_args_list[1].kwargs["data"])["token"].startswith("__RIS_ENC{")
    saved.assert_called_once_with("https://example.test/shterm/", {"SESSION": "test"})


def test_targets_follow_pagination():
    http = Mock()
    http.get.return_value = response(data={})
    http.put.side_effect = [response(data={"content": [{"id": 1}], "last": False}), response(data={"content": [{"id": 2}], "last": True})]
    assert ShtermClient("https://example.test/shterm/", http).targets() == [{"id": 1}, {"id": 2}]
    assert http.put.call_count == 2
