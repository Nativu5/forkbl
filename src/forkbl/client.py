"""HTTP client for the shterm web application."""

from __future__ import annotations

import getpass
import re
import sys
from urllib.parse import urljoin

import requests
import truststore

from .crypto import encrypt_field
from .config import normalize_url
from .payload import decode_access_url
from .session import save_session


# Use the macOS/Linux system trust store so enterprise certificates accepted by
# the browser are accepted by the CLI as well.
truststore.inject_into_ssl()


SESSION_ID_RE = re.compile(r"sessionId\s*=\s*['\"]([^'\"]+)")
CSRF_RE = re.compile(r'<input[^>]+name=["\']_csrf["\'][^>]+value=["\']([^"\']+)', re.I)


class ShtermClient:
    def __init__(self, base_url: str, http: requests.Session | None = None, verbose: bool = False):
        self.base_url = normalize_url(base_url)
        self.http = http or requests.Session()
        self.verbose = verbose

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    def _request(self, method: str, path: str, **kwargs):
        self._debug(f"{method.upper()} {path}")
        try:
            response = getattr(self.http, method.lower())(self._url(path), **kwargs)
        except requests.Timeout as exc:
            raise RuntimeError("request timed out; check the network and try again") from exc
        except requests.ConnectionError as exc:
            raise RuntimeError("could not connect to the shterm server") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"HTTP request failed: {exc}") from exc
        self._debug(f"HTTP {response.status_code} {path}")
        return response

    @staticmethod
    def _check_response(response, action: str) -> None:
        if response.status_code < 400:
            return
        messages = {
            401: "login session expired; run `forkbl login` again",
            403: "the server denied this operation",
            404: "the requested shterm endpoint was not found",
        }
        message = messages.get(response.status_code, f"{action} failed (HTTP {response.status_code})")
        raise RuntimeError(message)

    def _debug(self, message: str) -> None:
        if self.verbose:
            print(f"[forkbl] {message}", file=sys.stderr, flush=True)

    def _login_page(self, suffix: str = "login") -> tuple[str, str]:
        response = self._request("GET", suffix, timeout=20)
        self._check_response(response, "loading the login page")
        csrf = CSRF_RE.search(response.text)
        session_id = SESSION_ID_RE.search(response.text)
        if not csrf or not session_id:
            raise RuntimeError("could not find CSRF token or session ID in login page")
        return csrf.group(1), session_id.group(1)

    def login(self, username: str, password: str, token: str | None = None) -> None:
        csrf, session_id = self._login_page()
        form = [
            ("_csrf", csrf),
            ("_csrf", csrf),
            ("username", username),
            ("password", encrypt_field(password, session_id)),
            ("captcha", ""),
            ("captchaPage", ""),
        ]
        response = self._request("POST", "login", data=form, allow_redirects=False, timeout=20)
        if response.status_code not in {302, 303}:
            raise RuntimeError(f"login rejected (HTTP {response.status_code})")
        location = response.headers.get("Location", "")
        if "tokenRequest" in location:
            csrf, session_id = self._login_page("login?tokenRequest")
            token = getpass.getpass("Dynamic token: ") if token is None else token
            form = [
                ("_csrf", csrf),
                ("token", encrypt_field(token, session_id)),
                ("username", username),
                ("password", encrypt_field(password, session_id)),
            ]
            response = self._request("POST", "login", data=form, allow_redirects=False, timeout=20)
            if response.status_code not in {302, 303}:
                raise RuntimeError(f"token authentication rejected (HTTP {response.status_code})")
        if "login" in response.headers.get("Location", "").lower():
            raise RuntimeError("authentication failed; check the password and dynamic token")
        save_session(self.base_url, self.http.cookies.get_dict())

    def logout(self) -> None:
        response = self._request("GET", "logout", allow_redirects=False, timeout=20)
        if response.status_code not in {200, 302, 303, 404}:
            raise RuntimeError(f"logout failed (HTTP {response.status_code})")

    @classmethod
    def from_saved(cls, base_url: str | None = None, verbose: bool = False) -> "ShtermClient":
        from .session import load_session

        saved_url, cookies = load_session()
        if base_url is not None and normalize_url(base_url) != normalize_url(saved_url):
            raise RuntimeError("server URL changed; run 'forkbl login' for the configured server first")
        client = cls(saved_url, verbose=verbose)
        client.http.cookies.update(cookies)
        return client

    def targets(self) -> list[dict]:
        tree = self._request("GET", "api/asset/getAccessViewTree", timeout=20)
        self._check_response(tree, "loading the target tree")
        rows: list[dict] = []
        page, size = 0, 100
        while True:
            response = self._request(
                "PUT",
                f"api/asset/getAccessViewDevs?page={page}&size={size}&sort=name,asc",
                json={"page": page, "size": size, "sort": "name,asc", "stateIn": "0", "paths": ["root"]},
                timeout=20,
            )
            self._check_response(response, "loading targets")
            data = response.json()
            content = data.get("content", [])
            rows.extend(content)
            if data.get("last", True) or not content:
                break
            page += 1
        return rows

    def access_payload(self, device_id: int, account: str) -> dict:
        check = self._request("POST", "api/asset/checkServ", json={"devId": device_id, "service": "ssh"}, timeout=20)
        self._check_response(check, "checking SSH access")
        response = self._request(
            "POST",
            "api/deviceAccess/accessUrl",
            json={
                "misc": {
                    "resolution": "80x24",
                    "tab": True,
                    "recheckCode": "",
                    "win2008IpListStr": "",
                    "isDualAuth": False,
                },
                "sessRemark": "",
                "account": account,
                "proto": "ssh",
                "dev": device_id,
            },
            timeout=20,
        )
        self._check_response(response, "requesting SSH access")
        access_url = response.json()["url"]
        self._debug(f"access URL: {access_url}")
        return decode_access_url(access_url)

    def default_account(self, device_id: int, device: dict) -> str:
        """Resolve the account selected by shterm for a device."""
        response = self._request("GET", f"api/servSys/getLoginUserAccessDevConfig/{device_id}/-1", timeout=20)
        if response.ok:
            configured = response.json().get("defaultAcc", "")
            if configured.startswith("*"):
                configured = configured[1:]
            if configured:
                return configured
        accounts = device.get("accounts", {}).get("accounts", [])
        account = device.get("sysType", {}).get("privAccount") or (accounts[0].get("name") if accounts else "")
        if not account:
            raise RuntimeError("target has no usable account")
        return account

    def login_interactive(self) -> None:
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        self.login(username, password)
