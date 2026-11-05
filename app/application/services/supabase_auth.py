from __future__ import annotations

import base64
from dataclasses import dataclass, field
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
import threading
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
import webbrowser

from keyring.errors import KeyringError
from keyring.backends.Windows import WinVaultKeyring
import requests

from app.config import (
    SUPABASE_PROJECT_URL,
    get_setting,
)


KEYRING_SERVICE = "Clipstream.Supabase"
KEYRING_REFRESH_TOKEN = "refresh-token"
OAUTH_CALLBACK_HOST = "127.0.0.1"
OAUTH_CALLBACK_PORT = 8765
OAUTH_CALLBACK_PATH = "/auth/callback"
OAUTH_CALLBACK_TIMEOUT_SECONDS = 180
_CREDENTIAL_STORE = WinVaultKeyring()


class SupabaseAuthError(Exception):
    pass


@dataclass(frozen=True)
class AuthSession:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    user_id: str
    email: str | None
    display_name: str | None


class _OAuthCallbackServer(HTTPServer):
    def __init__(self, expected_state: str):
        super().__init__((OAUTH_CALLBACK_HOST, OAUTH_CALLBACK_PORT), _OAuthCallbackHandler)
        self.expected_state = expected_state
        self.expected_callback_path = f"{OAUTH_CALLBACK_PATH}/{expected_state}"
        self.result: tuple[str | None, str | None] | None = None
        self.result_ready = threading.Event()


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    server: _OAuthCallbackServer

    def do_GET(self):
        parsed_url = urlsplit(self.path)
        if parsed_url.path != self.server.expected_callback_path:
            self.send_error(404)
            return

        query = parse_qs(parsed_url.query)
        error = query.get("error_description", query.get("error", [None]))[0]
        code = query.get("code", [None])[0]
        self.server.result = (code, error)
        self.server.result_ready.set()
        self.send_response(200 if code and not error else 400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        message = (
            "Google sign-in complete. You can close this window."
            if code and not error
            else "Google sign-in could not be completed. Return to Clipstream."
        )
        self.wfile.write(
            (
                "<!doctype html><html><meta charset='utf-8'>"
                f"<title>Clipstream</title><body><p>{message}</p></body></html>"
            ).encode("utf-8")
        )

    def log_message(self, _format: str, *args: Any):
        del _format, args
        return


def _base_url() -> str:
    url = get_setting("SUPABASE_URL", SUPABASE_PROJECT_URL)
    if not url or urlsplit(url).scheme != "https":
        raise SupabaseAuthError(
            "Supabase URL is not configured correctly."
        )
    return url.rstrip("/")


def _publishable_key() -> str:
    key = get_setting("SUPABASE_PUBLISHABLE_KEY")
    if not key:
        raise SupabaseAuthError("The Supabase publishable key is not configured.")
    return key


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(sha256(verifier.encode("ascii")).digest())
    return verifier, challenge.rstrip(b"=").decode("ascii")


def _response_payload(response: requests.Response) -> dict[str, Any]:
    if response.ok and not response.content:
        return {}
    try:
        payload = response.json()
    except ValueError as exc:
        raise SupabaseAuthError("Supabase returned an unreadable response.") from exc
    if not isinstance(payload, dict):
        raise SupabaseAuthError("Supabase returned an invalid response.")
    if not response.ok:
        detail = (
            payload.get("msg")
            or payload.get("message")
            or payload.get("error_description")
            or payload.get("error")
        )
        raise SupabaseAuthError(
            f"Supabase authentication failed: {detail or response.status_code}"
        )
    return payload


class SupabaseAuthClient:
    def __init__(self):
        self._session: AuthSession | None = None

    def sign_in_with_google(self) -> AuthSession:
        base_url = _base_url()
        publishable_key = _publishable_key()
        verifier, challenge = _pkce_pair()
        state = secrets.token_urlsafe(32)
        callback_url = (
            f"http://{OAUTH_CALLBACK_HOST}:{OAUTH_CALLBACK_PORT}"
            f"{OAUTH_CALLBACK_PATH}/{state}"
        )
        authorization_url = f"{base_url}/auth/v1/authorize?" + urlencode(
            {
                "provider": "google",
                "redirect_to": callback_url,
                "code_challenge": challenge,
                "code_challenge_method": "s256",
                "apikey": publishable_key,
            }
        )

        try:
            server = _OAuthCallbackServer(state)
        except OSError as exc:
            raise SupabaseAuthError(
                f"Could not open the sign-in callback on port {OAUTH_CALLBACK_PORT}."
            ) from exc

        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            if not webbrowser.open(authorization_url, new=2):
                raise SupabaseAuthError(
                    "Could not open a browser for Google sign-in."
                )
            if not server.result_ready.wait(OAUTH_CALLBACK_TIMEOUT_SECONDS):
                raise SupabaseAuthError(
                    "Google sign-in timed out. Please try again."
                )
            code, callback_error = server.result or (None, None)
            if callback_error:
                raise SupabaseAuthError(
                    f"Google sign-in was not completed: {callback_error}"
                )
            if not code:
                raise SupabaseAuthError(
                    "Google sign-in returned no authorization code."
                )
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)

        try:
            response = requests.post(
                f"{base_url}/auth/v1/token",
                params={"grant_type": "pkce"},
                headers={"apikey": publishable_key},
                json={"auth_code": code, "code_verifier": verifier},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise SupabaseAuthError(
                "Could not exchange the Google sign-in code with Supabase."
            ) from exc
        return self._store_session(_response_payload(response))

    def restore_session(self) -> AuthSession | None:
        try:
            refresh_token = _CREDENTIAL_STORE.get_password(
                KEYRING_SERVICE,
                KEYRING_REFRESH_TOKEN,
            )
        except KeyringError as exc:
            raise SupabaseAuthError(
                "Could not read the session from the Windows credential store."
            ) from exc
        if not refresh_token:
            return None

        base_url = _base_url()
        publishable_key = _publishable_key()
        try:
            response = requests.post(
                f"{base_url}/auth/v1/token",
                params={"grant_type": "refresh_token"},
                headers={"apikey": publishable_key},
                json={"refresh_token": refresh_token},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise SupabaseAuthError("Could not restore the Google account session.") from exc
        return self._store_session(_response_payload(response))

    def sign_out(self):
        session = self._session or self.restore_session()
        if session is None:
            return

        base_url = _base_url()
        publishable_key = _publishable_key()
        try:
            response = requests.post(
                f"{base_url}/auth/v1/logout",
                params={"scope": "local"},
                headers={
                    "apikey": publishable_key,
                    "Authorization": f"Bearer {session.access_token}",
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            raise SupabaseAuthError("Could not sign out from Supabase.") from exc
        _response_payload(response)
        try:
            _CREDENTIAL_STORE.delete_password(KEYRING_SERVICE, KEYRING_REFRESH_TOKEN)
        except KeyringError as exc:
            raise SupabaseAuthError(
                "Could not remove the session from the Windows credential store."
            ) from exc
        self._session = None

    def _store_session(self, payload: dict[str, Any]) -> AuthSession:
        user = payload.get("user")
        if not isinstance(user, dict):
            raise SupabaseAuthError("Supabase did not return an authenticated user.")
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        user_id = user.get("id")
        if not isinstance(access_token, str) or not access_token:
            raise SupabaseAuthError("Supabase returned an incomplete session.")
        if not isinstance(refresh_token, str) or not refresh_token:
            raise SupabaseAuthError("Supabase returned an incomplete session.")
        if not isinstance(user_id, str) or not user_id:
            raise SupabaseAuthError("Supabase returned an incomplete session.")

        metadata = user.get("user_metadata")
        display_name = None
        if isinstance(metadata, dict):
            display_name = metadata.get("full_name") or metadata.get("name")
        email = user.get("email")
        try:
            _CREDENTIAL_STORE.set_password(
                KEYRING_SERVICE,
                KEYRING_REFRESH_TOKEN,
                refresh_token,
            )
        except KeyringError as exc:
            raise SupabaseAuthError(
                "Could not save the session in the Windows credential store."
            ) from exc

        self._session = AuthSession(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user_id,
            email=email if isinstance(email, str) else None,
            display_name=display_name if isinstance(display_name, str) else None,
        )
        return self._session
