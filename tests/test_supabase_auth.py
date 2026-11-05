import base64
from hashlib import sha256
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from urllib.request import urlopen
import unittest
from unittest.mock import Mock, patch

from app.application.services.supabase_auth import (
    KEYRING_REFRESH_TOKEN,
    KEYRING_SERVICE,
    SupabaseAuthClient,
    _pkce_pair,
)


class SupabaseAuthTests(unittest.TestCase):
    @patch("app.application.services.supabase_auth._CREDENTIAL_STORE.set_password")
    @patch("app.application.services.supabase_auth.requests.post")
    @patch("app.application.services.supabase_auth.webbrowser.open")
    @patch("app.application.services.supabase_auth.get_setting")
    def test_google_sign_in_uses_pkce_and_persists_refresh_token_in_keyring(
        self,
        get_setting,
        open_browser,
        post,
        set_password,
    ):
        get_setting.side_effect = {
            "SUPABASE_URL": "https://sample.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_sample",
        }.get
        response = Mock(
            ok=True,
            content=b'{"access_token":"access","refresh_token":"refresh"}',
        )
        response.json.return_value = {
            "access_token": "access",
            "refresh_token": "refresh",
            "user": {
                "id": "user-1",
                "email": "user@example.com",
                "user_metadata": {"full_name": "Sample User"},
            },
        }
        post.return_value = response

        def finish_oauth(authorization_url, new):
            self.assertEqual(new, 2)
            authorization = parse_qs(urlsplit(authorization_url).query)
            redirect = urlsplit(authorization["redirect_to"][0])
            callback_url = urlunsplit(
                (
                    redirect.scheme,
                    redirect.netloc,
                    redirect.path,
                    urlencode({"code": "auth-code"}),
                    "",
                )
            )
            with urlopen(callback_url, timeout=5) as callback_response:
                self.assertEqual(callback_response.status, 200)
            self.assertEqual(authorization["provider"], ["google"])
            self.assertEqual(authorization["code_challenge_method"], ["s256"])
            self.assertEqual(len(authorization["code_challenge"][0]), 43)
            return True

        open_browser.side_effect = finish_oauth
        session = SupabaseAuthClient().sign_in_with_google()

        self.assertEqual(session.user_id, "user-1")
        self.assertEqual(session.email, "user@example.com")
        self.assertEqual(session.display_name, "Sample User")
        self.assertNotIn("access", repr(session))
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://sample.supabase.co/auth/v1/token")
        self.assertEqual(kwargs["params"], {"grant_type": "pkce"})
        self.assertEqual(kwargs["json"]["auth_code"], "auth-code")
        self.assertEqual(kwargs["headers"]["apikey"], "sb_publishable_sample")
        set_password.assert_called_once_with(
            KEYRING_SERVICE,
            KEYRING_REFRESH_TOKEN,
            "refresh",
        )

    @patch("app.application.services.supabase_auth._CREDENTIAL_STORE.set_password")
    @patch("app.application.services.supabase_auth._CREDENTIAL_STORE.get_password")
    @patch("app.application.services.supabase_auth.requests.post")
    @patch("app.application.services.supabase_auth.get_setting")
    def test_restore_rotates_refresh_token_in_credential_store(
        self,
        get_setting,
        post,
        get_password,
        set_password,
    ):
        get_setting.side_effect = {
            "SUPABASE_URL": "https://sample.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_sample",
        }.get
        get_password.return_value = "old-refresh"
        response = Mock(
            ok=True,
            content=b'{"access_token":"access","refresh_token":"new-refresh"}',
        )
        response.json.return_value = {
            "access_token": "access",
            "refresh_token": "new-refresh",
            "user": {"id": "user-1", "email": "user@example.com"},
        }
        post.return_value = response

        session = SupabaseAuthClient().restore_session()

        self.assertEqual(session.email, "user@example.com")
        self.assertEqual(post.call_args.kwargs["json"], {"refresh_token": "old-refresh"})
        set_password.assert_called_once_with(
            KEYRING_SERVICE,
            KEYRING_REFRESH_TOKEN,
            "new-refresh",
        )

    @patch("app.application.services.supabase_auth._CREDENTIAL_STORE.delete_password")
    @patch("app.application.services.supabase_auth.requests.post")
    @patch("app.application.services.supabase_auth.get_setting")
    def test_sign_out_revokes_session_and_removes_refresh_token(
        self,
        get_setting,
        post,
        delete_password,
    ):
        get_setting.side_effect = {
            "SUPABASE_URL": "https://sample.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_sample",
        }.get
        response = Mock(ok=True, content=b"")
        post.return_value = response
        client = SupabaseAuthClient()
        client._session = client._store_session(
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "user": {"id": "user-1"},
            }
        )

        client.sign_out()

        self.assertEqual(post.call_args.args[0], "https://sample.supabase.co/auth/v1/logout")
        self.assertEqual(post.call_args.kwargs["params"], {"scope": "local"})
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer access",
        )
        delete_password.assert_called_once_with(
            KEYRING_SERVICE,
            KEYRING_REFRESH_TOKEN,
        )
        self.assertIsNone(client._session)

    def test_pkce_challenge_matches_verifier(self):
        verifier, challenge = _pkce_pair()
        expected = base64.urlsafe_b64encode(sha256(verifier.encode()).digest())

        self.assertEqual(challenge, expected.rstrip(b"=").decode())
        self.assertGreaterEqual(len(verifier), 43)
