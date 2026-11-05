from __future__ import annotations

import asyncio
import sys
from typing import Callable

import flet as ft

from app.application.services.country_analytics import (
    UsageAnalyticsError,
    lookup_country_code,
    record_country_usage_for_country,
)
from app.application.services.supabase_auth import (
    SupabaseAuthClient,
    SupabaseAuthError,
)
from app.config import (
    downloads_dir,
    get_country_analytics_enabled,
    save_country_analytics_enabled,
)
from app.presentation.components import PresentationComponents


class SettingsView(PresentationComponents):
    page: ft.Page
    file_picker: ft.FilePicker
    output_folder: str
    output_dir_field: ft.Text
    toggle_theme: Callable[[], None]
    supabase_auth: SupabaseAuthClient

    def show_settings(self):
        output_folder = getattr(self, "output_folder", downloads_dir())
        self.folder_field = ft.TextField(
            label="Download folder",
            value=output_folder,
            expand=True,
            read_only=True,
            prefix_icon=ft.Icons.FOLDER,
            border_radius=10,
        )
        browse_button = ft.OutlinedButton(
            "Browse",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._on_browse_folder,
        )

        current_mode = self._t(
            "Dark" if self.page.theme_mode == ft.ThemeMode.DARK else "Light"
        )
        self.theme_label = ft.Text(
            f"{self._t('Current theme: ')}{current_mode}",
            size=14,
        )
        self.theme_switch = ft.Switch(
            label="Dark mode",
            value=self.page.theme_mode == ft.ThemeMode.DARK,
            active_color=ft.Colors.INDIGO,
            on_change=self._on_theme_switch,
        )
        self.language_dropdown = ft.Dropdown(
            label="Language",
            value=self.language,
            options=[
                ft.dropdown.Option("es", "Spanish"),
                ft.dropdown.Option("en-US", "English (United States)"),
            ],
            on_select=self._on_language_select,
            width=320,
        )
        self.account_status = ft.Text(
            self._t(
                getattr(
                    self,
                    "_account_status_message",
                    "Guest mode. No account is signed in.",
                )
            ),
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.google_sign_in_button = ft.FilledButton(
            "Continue with Google",
            icon=ft.Icons.LOGIN,
            on_click=self._on_google_sign_in,
        )
        self.sign_out_button = ft.OutlinedButton(
            "Sign out",
            icon=ft.Icons.LOGOUT,
            visible=getattr(self, "_account_signed_in", False),
            on_click=self._on_sign_out,
        )
        self.google_sign_in_button.visible = not getattr(
            self,
            "_account_signed_in",
            False,
        )
        self.country_analytics_switch = ft.Switch(
            label="Share anonymous country statistics",
            value=get_country_analytics_enabled(),
            active_color=ft.Colors.INDIGO,
            on_change=self._on_country_analytics_switch,
        )
        self.country_analytics_status = ft.Text(
            self._t(
                getattr(
                    self,
                    "_country_analytics_status_message",
                    "Country not checked.",
                )
            ),
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )

        about_card = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.INDIGO),
                        ft.Text("About", size=18, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8,
                ),
                ft.Divider(height=1, thickness=1, opacity=0.15),
                ft.Text(
                    "Clipstream  v1.0.0",
                    size=14,
                    weight=ft.FontWeight.W_500,
                ),
                ft.Text(
                    "Flet interface connected to yt-dlp, Lamovie, Markdown, "
                    "and torrent services.",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Text(
                    f"Python {sys.version.split()[0]}  ·  Flet {ft.__version__}",
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    italic=True,
                ),
            ],
            spacing=8,
        )

        self._render_page(
            ft.Column(
                [
                    self._section_heading(
                        "Settings",
                        "Set the download folder, language, and appearance.",
                        ft.Icons.SETTINGS_OUTLINED,
                    ),
                    self._surface(
                        ft.Column(
                            [
                                ft.Text(
                                    "Language",
                                    size=15,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    "Choose the interface language.",
                                    size=13,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                                self.language_dropdown,
                            ],
                            spacing=8,
                        ),
                        padding=24,
                    ),
                    self._surface(
                        ft.Column(
                            [
                                ft.Text(
                                    "Account",
                                    size=15,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    "The app remains available in guest mode. "
                                    "Google sign-in is optional and prepares your "
                                    "account for future synced features.",
                                    size=13,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                                self.account_status,
                                ft.Row(
                                    [
                                        self.google_sign_in_button,
                                        self.sign_out_button,
                                    ],
                                    spacing=10,
                                ),
                            ],
                            spacing=8,
                        ),
                        padding=24,
                    ),
                    self._surface(
                        ft.Column(
                            [
                                ft.Text(
                                    "Usage statistics",
                                    size=15,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    "The footer estimates your country from your "
                                    "public IP using api.country.is. This service "
                                    "processes your IP to identify the country. "
                                    "When enabled, anonymous statistics send only "
                                    "your country code and app version to Supabase; "
                                    "your IP is never sent there.",
                                    size=13,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                                self.country_analytics_switch,
                                self.country_analytics_status,
                            ],
                            spacing=8,
                        ),
                        padding=24,
                    ),
                    self._surface(
                        ft.Column(
                            [
                                ft.Text(
                                    "Destination folder",
                                    size=15,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Row(
                                    [self.folder_field, browse_button],
                                    spacing=10,
                                ),
                            ],
                            spacing=12,
                        ),
                        padding=24,
                    ),
                    self._surface(
                        ft.Column(
                            [
                                ft.Text(
                                    "Appearance",
                                    size=15,
                                    weight=ft.FontWeight.W_600,
                                ),
                                self.theme_switch,
                                self.theme_label,
                            ],
                            spacing=8,
                        ),
                        padding=24,
                    ),
                    self._surface(about_card, padding=24),
                ],
                spacing=20,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            )
        )
        if self.country_analytics_switch.value:
            self._schedule_country_analytics()

    def _schedule_country_analytics(self):
        if getattr(self, "_country_analytics_recorded", False) or getattr(
            self, "_country_analytics_in_progress", False
        ):
            return
        run_task = getattr(self.page, "run_task", None)
        if run_task is not None:
            self._country_analytics_in_progress = True
            run_task(self._record_country_usage)

    def _schedule_footer_country_lookup(self):
        if getattr(self, "_footer_country_lookup_in_progress", False):
            return
        run_task = getattr(self.page, "run_task", None)
        if run_task is not None:
            self._footer_country_lookup_in_progress = True
            run_task(self._load_footer_country)

    async def _load_footer_country(self):
        try:
            country_code = await asyncio.to_thread(lookup_country_code)
        except UsageAnalyticsError:
            self._footer_country_lookup_in_progress = False
            self._set_footer_country("Country unavailable.")
            return
        self._footer_country_lookup_in_progress = False
        self._set_country_code(country_code)

    def _set_footer_country(self, message: str):
        self._footer_country_message = message
        label = getattr(self, "footer_country_label", None)
        if label is not None:
            label.value = self._t(message)
            self.page.update()

    def _schedule_auth_restore(self):
        run_task = getattr(self.page, "run_task", None)
        if run_task is not None:
            run_task(self._restore_auth_session)

    async def _restore_auth_session(self):
        try:
            session = await asyncio.to_thread(
                self.supabase_auth.restore_session
            )
        except SupabaseAuthError as exc:
            self._set_account_status("Could not restore account: " + str(exc))
            return
        if session is not None:
            identity = session.display_name or session.email or session.user_id
            self._set_account_state(True, "Signed in as: " + identity)

    async def _on_google_sign_in(self, _event=None):
        self.google_sign_in_button.disabled = True
        self._set_account_status("Waiting for Google sign-in...")
        try:
            session = await asyncio.to_thread(
                self.supabase_auth.sign_in_with_google
            )
        except SupabaseAuthError as exc:
            self._set_account_status("Could not sign in: " + str(exc))
        else:
            identity = session.display_name or session.email or session.user_id
            self._set_account_state(True, "Signed in as: " + identity)
        finally:
            self.google_sign_in_button.disabled = getattr(
                self,
                "_account_signed_in",
                False,
            )
            self.page.update()

    async def _on_sign_out(self, _event=None):
        self.sign_out_button.disabled = True
        try:
            await asyncio.to_thread(self.supabase_auth.sign_out)
        except SupabaseAuthError as exc:
            self._set_account_status("Could not sign out: " + str(exc))
        else:
            self._set_account_state(
                False,
                "Guest mode. No account is signed in.",
            )
        finally:
            self.sign_out_button.disabled = not getattr(
                self,
                "_account_signed_in",
                False,
            )
            self.page.update()

    def _set_account_state(self, signed_in: bool, message: str):
        self._account_signed_in = signed_in
        self._set_account_status(message)
        indicator = getattr(self, "account_indicator", None)
        if indicator is not None:
            identity = message.removeprefix("Signed in as: ")
            indicator.content = self._t("Account" if signed_in else "Guest")
            indicator.icon = (
                ft.Icons.ACCOUNT_CIRCLE_OUTLINED
                if signed_in
                else ft.Icons.PERSON_OUTLINE
            )
            indicator.tooltip = self._t(
                "Signed in as: " + identity
                if signed_in
                else "Guest account"
            )
        sign_in_button = getattr(self, "google_sign_in_button", None)
        sign_out_button = getattr(self, "sign_out_button", None)
        if sign_in_button is not None:
            sign_in_button.visible = not signed_in
            sign_in_button.disabled = False
        if sign_out_button is not None:
            sign_out_button.visible = signed_in
            sign_out_button.disabled = False
        self.page.update()

    def _set_account_status(self, message: str):
        self._account_status_message = message
        status = getattr(self, "account_status", None)
        if status is not None:
            status.value = self._t(message)
            self.page.update()

    async def _on_country_analytics_switch(self, event):
        enabled = event.control.value is True
        try:
            save_country_analytics_enabled(enabled)
        except (OSError, ValueError) as exc:
            event.control.value = not enabled
            self._show_message(
                self._t(f"Could not save analytics preference: {exc}"),
                ft.Colors.RED_200,
            )
            return

        if enabled:
            await self._record_country_usage()
        else:
            self._set_country_analytics_status("Country statistics are disabled.")

    async def _record_country_usage(self):
        if getattr(self, "_country_analytics_recorded", False):
            country_code = self._country_analytics_country
            self._set_country_analytics_status(
                "Connected from country: " + country_code
            )
            return
        self._country_analytics_in_progress = True
        self._set_country_analytics_status("Checking country...")
        try:
            country_code = getattr(self, "_footer_country_code", None)
            if country_code is None:
                country_code = await asyncio.to_thread(lookup_country_code)
                self._set_country_code(country_code)
            await asyncio.to_thread(
                record_country_usage_for_country,
                country_code,
            )
        except UsageAnalyticsError as exc:
            self._country_analytics_in_progress = False
            self._set_country_analytics_status(
                "Could not record country statistics: " + str(exc)
            )
            return
        self._country_analytics_recorded = True
        self._country_analytics_in_progress = False
        self._country_analytics_country = country_code
        self._set_country_code(country_code)
        self._set_country_analytics_status(
            "Connected from country: " + country_code
        )

    def _set_country_code(self, country_code: str):
        self._footer_country_code = country_code
        self._set_footer_country("Country: " + country_code)

    def _set_country_analytics_status(self, message: str):
        self._country_analytics_status_message = message
        status = getattr(self, "country_analytics_status", None)
        if status is not None:
            status.value = self._t(message)
            self.page.update()

    async def _on_browse_folder(self, _e=None):
        selected = await self.file_picker.get_directory_path(
            dialog_title="Select the download folder",
            initial_directory=self.folder_field.value,
        )
        if not selected:
            return

        self.output_folder = selected
        self.folder_field.value = selected
        if hasattr(self, "output_dir_field"):
            self.output_dir_field.value = self._t(f"Destination: {selected}")
        self.page.update()

    def _on_language_select(self, e):
        selected = e.control.value
        if selected in {"es", "en-US"}:
            self.change_language(selected)

    def _on_theme_switch(self, _e=None):
        self.toggle_theme()
        mode = self._t(
            "Dark" if self.page.theme_mode == ft.ThemeMode.DARK else "Light"
        )
        self.theme_label.value = f"{self._t('Current theme: ')}{mode}"
        self.theme_switch.value = self.page.theme_mode == ft.ThemeMode.DARK
        self.page.update()
