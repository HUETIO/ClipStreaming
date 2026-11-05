import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock, patch

import flet as ft

from app.application.services import country_analytics
from app.config import get_country_analytics_enabled, save_country_analytics_enabled
from app.presentation.app import YouTuberDownloaderApp


class CountryAnalyticsConfigTests(unittest.TestCase):
    def test_preference_defaults_to_disabled_and_preserves_existing_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            preference_file = Path(temp_dir) / "settings.json"
            with patch("app.config.USER_SETTINGS_PATH", preference_file):
                self.assertFalse(get_country_analytics_enabled())
                preference_file.write_text(
                    json.dumps({"language": "en-US"}),
                    encoding="utf-8",
                )

                save_country_analytics_enabled(True)

                self.assertTrue(get_country_analytics_enabled())
                self.assertEqual(
                    json.loads(preference_file.read_text(encoding="utf-8")),
                    {"language": "en-US", "country_analytics_enabled": True},
                )

    def test_rejects_non_boolean_preference(self):
        with self.assertRaises(ValueError):
            save_country_analytics_enabled("yes")


class CountryAnalyticsServiceTests(unittest.TestCase):
    @patch("app.application.services.country_analytics.requests.post")
    @patch("app.application.services.country_analytics.requests.get")
    @patch("app.application.services.country_analytics.get_setting")
    def test_records_only_country_code_and_version(
        self,
        get_setting,
        get_country,
        post_event,
    ):
        get_setting.side_effect = {
            "SUPABASE_URL": "https://sample.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_sample",
        }.get
        get_country.return_value.json.return_value = {"ip": "192.0.2.1", "country": "ES"}
        get_country.return_value.raise_for_status.return_value = None
        post_event.return_value.raise_for_status.return_value = None

        result = country_analytics.record_country_usage()

        self.assertEqual(result, "ES")
        post_event.assert_called_once()
        args, kwargs = post_event.call_args
        self.assertEqual(
            args[0],
            "https://sample.supabase.co/rest/v1/app_usage_events",
        )
        self.assertEqual(
            kwargs["json"],
            {"country_code": "ES", "app_version": country_analytics.APP_VERSION},
        )
        self.assertNotIn("ip", kwargs["json"])
        self.assertEqual(kwargs["headers"]["apikey"], "sb_publishable_sample")

    @patch("app.application.services.country_analytics.requests.post")
    @patch("app.application.services.country_analytics.requests.get")
    @patch("app.application.services.country_analytics.get_setting")
    def test_does_not_send_event_if_country_lookup_fails(
        self,
        get_setting,
        get_country,
        post_event,
    ):
        get_setting.side_effect = {
            "SUPABASE_URL": "https://sample.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_sample",
        }.get
        get_country.return_value.json.return_value = {"country": "Spain"}

        with self.assertRaises(country_analytics.UsageAnalyticsError):
            country_analytics.record_country_usage()

        post_event.assert_not_called()


class CountryAnalyticsSettingsTests(unittest.TestCase):
    @patch("app.presentation.settings.lookup_country_code", return_value="MX")
    def test_footer_shows_country_code_without_exposing_ip(self, lookup_country):
        page = cast(
            ft.Page,
            SimpleNamespace(
                window=SimpleNamespace(),
                services=[],
                add=Mock(),
                update=Mock(),
                show_dialog=Mock(),
                pop_dialog=Mock(),
            ),
        )
        app = YouTuberDownloaderApp(page)

        asyncio.run(app._load_footer_country())

        lookup_country.assert_called_once_with()
        self.assertEqual(app.footer_country_label.value, "País: MX")
        self.assertNotIn("ip", app.footer_country_label.value.lower())

    def test_header_account_indicator_tracks_guest_and_signed_in_states(self):
        page = cast(
            ft.Page,
            SimpleNamespace(
                window=SimpleNamespace(),
                services=[],
                add=Mock(),
                update=Mock(),
                show_dialog=Mock(),
                pop_dialog=Mock(),
            ),
        )
        app = YouTuberDownloaderApp(page)

        self.assertIn(app.account_indicator, page.appbar.actions)
        self.assertEqual(app.account_indicator.content, "Invitado")
        self.assertEqual(app.account_indicator.icon, ft.Icons.PERSON_OUTLINE)

        app._set_account_state(True, "Signed in as: user@example.com")

        self.assertEqual(app.account_indicator.content, "Cuenta")
        self.assertEqual(
            app.account_indicator.icon,
            ft.Icons.ACCOUNT_CIRCLE_OUTLINED,
        )
        self.assertEqual(
            app.account_indicator.tooltip,
            "Sesión iniciada como: user@example.com",
        )

        app._set_account_state(False, "Guest mode. No account is signed in.")

        self.assertEqual(app.account_indicator.content, "Invitado")
        self.assertEqual(app.account_indicator.icon, ft.Icons.PERSON_OUTLINE)
        self.assertEqual(app.account_indicator.tooltip, "Cuenta de invitado")

    def test_header_account_indicator_opens_account_settings(self):
        page = cast(
            ft.Page,
            SimpleNamespace(
                window=SimpleNamespace(),
                services=[],
                add=Mock(),
                update=Mock(),
                show_dialog=Mock(),
                pop_dialog=Mock(),
            ),
        )
        app = YouTuberDownloaderApp(page)

        app._open_account_settings()

        self.assertEqual(app.nav_rail.selected_index, 4)
        self.assertTrue(
            any(
                isinstance(control, ft.Text) and control.value == "Cuenta"
                for surface in app.main_container.content.controls
                if isinstance(surface, ft.Container)
                and isinstance(surface.content, ft.Column)
                for control in surface.content.controls
            )
        )

    def test_country_statistics_switch_is_off_by_default(self):
        page = cast(
            ft.Page,
            SimpleNamespace(
                window=SimpleNamespace(),
                services=[],
                add=Mock(),
                update=Mock(),
                show_dialog=Mock(),
                pop_dialog=Mock(),
            ),
        )
        app = YouTuberDownloaderApp(page)

        app.show_settings()

        self.assertFalse(app.country_analytics_switch.value)
        self.assertEqual(app.country_analytics_status.value, "País sin consultar.")
        self.assertTrue(app.google_sign_in_button.visible)
        self.assertFalse(app.sign_out_button.visible)
        self.assertEqual(
            app.account_status.value,
            "Modo invitado. No hay ninguna cuenta iniciada.",
        )

    @patch("app.presentation.settings.lookup_country_code", return_value="ES")
    @patch("app.presentation.settings.record_country_usage_for_country")
    @patch("app.presentation.app.get_country_analytics_enabled", return_value=True)
    def test_existing_opt_in_records_usage_at_startup(
        self,
        _get_preference,
        _record_usage,
        _lookup_country,
    ):
        page = cast(
            ft.Page,
            SimpleNamespace(
                window=SimpleNamespace(),
                services=[],
                add=Mock(),
                update=Mock(),
                show_dialog=Mock(),
                pop_dialog=Mock(),
            ),
        )
        page.run_task = Mock(side_effect=lambda handler: asyncio.run(handler()))

        app = YouTuberDownloaderApp(page)

        self.assertEqual(
            app._country_analytics_status_message,
            "Connected from country: ES",
        )
        self.assertEqual(
            app._footer_country_message,
            "Country: ES",
        )
        app.show_settings()
        self.assertEqual(app.country_analytics_status.value, "País de conexión: ES")

    @patch("app.presentation.settings.lookup_country_code", return_value="ES")
    @patch("app.presentation.settings.record_country_usage_for_country")
    @patch("app.presentation.settings.save_country_analytics_enabled")
    def test_opt_in_records_country_and_updates_the_label(
        self,
        save_preference,
        record_usage,
        lookup_country,
    ):
        page = cast(
            ft.Page,
            SimpleNamespace(
                window=SimpleNamespace(),
                services=[],
                add=Mock(),
                update=Mock(),
                show_dialog=Mock(),
                pop_dialog=Mock(),
            ),
        )
        app = YouTuberDownloaderApp(page)
        app.show_settings()
        app.country_analytics_switch.value = True

        asyncio.run(
            app._on_country_analytics_switch(
                SimpleNamespace(control=app.country_analytics_switch)
            )
        )

        save_preference.assert_called_once_with(True)
        lookup_country.assert_called_once_with()
        record_usage.assert_called_once_with("ES")
        self.assertEqual(app.country_analytics_status.value, "País de conexión: ES")
        self.assertEqual(app.footer_country_label.value, "País: ES")
