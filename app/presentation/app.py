from __future__ import annotations

from threading import Event

import flet as ft

from app.config import (
    downloads_dir,
    get_country_analytics_enabled,
    get_language,
    save_language,
)
from app.application.services.supabase_auth import SupabaseAuthClient
from app.infrastructure.video.video_lab import VideoLab
from app.presentation.components import PresentationComponents
from app.presentation.external_tools_view import ExternalToolsView
from app.presentation.settings import SettingsView
from app.presentation.video_lab_view import VideoLabView


class YouTuberDownloaderApp(
    VideoLabView,
    ExternalToolsView,
    SettingsView,
    PresentationComponents,
):
    def __init__(self, page: ft.Page):
        self.page = page
        self.language = get_language()
        self.supabase_auth = SupabaseAuthClient()
        page.title = "Clipstream"
        page.window.width = 1280
        page.window.height = 850
        page.window.min_width = 900
        page.window.min_height = 600
        page.padding = 0
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = ft.Colors.SURFACE
        page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO, use_material3=True)
        page.dark_theme = ft.Theme(
            color_scheme_seed=ft.Colors.INDIGO,
            use_material3=True,
        )
        page.vertical_alignment = ft.MainAxisAlignment.START
        page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH

        self.output_folder = downloads_dir()
        self.video_lab = VideoLab(self.output_folder)
        self.download_queue: list[dict] = []
        self._next_queue_id = 1
        self.download_running = False
        self._active_queue_item_id: int | None = None
        self.external_task_running = False
        self.torrent_download_running = False
        self.download_cancel_event = Event()
        self.file_picker = ft.FilePicker()
        page.services.append(self.file_picker)

        self.main_container = ft.Container(
            expand=True,
            padding=24,
            bgcolor=ft.Colors.SURFACE,
        )
        self.nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.VIDEO_LIBRARY_OUTLINED,
                    selected_icon=ft.Icons.VIDEO_LIBRARY,
                    label=self._t("Video Lab"),
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.MOVIE_OUTLINED,
                    selected_icon=ft.Icons.MOVIE,
                    label=self._t("Lamovie"),
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.DESCRIPTION_OUTLINED,
                    selected_icon=ft.Icons.DESCRIPTION,
                    label=self._t("Web to Markdown"),
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.DOWNLOAD_FOR_OFFLINE_OUTLINED,
                    selected_icon=ft.Icons.DOWNLOAD_FOR_OFFLINE,
                    label=self._t("Torrent"),
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label=self._t("Settings"),
                ),
            ],
            on_change=self.on_nav_change,
        )
        self.theme_icon_btn = ft.IconButton(
            icon=ft.Icons.DARK_MODE,
            tooltip=self._t("Change theme"),
            on_click=lambda _: self.toggle_theme(),
        )
        self.account_indicator = ft.TextButton(
            content=self._t("Guest"),
            icon=ft.Icons.PERSON_OUTLINE,
            tooltip=self._t("Guest account"),
            on_click=self._open_account_settings,
        )
        self.stop_download_button = ft.FilledButton(
            self._t("STOP"),
            icon=ft.Icons.STOP,
            bgcolor=ft.Colors.RED_700,
            color=ft.Colors.WHITE,
            disabled=True,
            visible=False,
            on_click=self.stop_active_download,
        )
        self.stop_download_area = ft.Container(
            content=self.stop_download_button,
            alignment=ft.Alignment.CENTER_RIGHT,
            padding=ft.Padding.symmetric(horizontal=24, vertical=8),
            visible=False,
        )

        page.appbar = ft.AppBar(
            title=ft.Text("Clipstream", weight=ft.FontWeight.BOLD),
            center_title=False,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            actions=[
                self.account_indicator,
                self.theme_icon_btn,
                ft.Container(width=12),
            ],
        )
        self.footer_tagline = ft.Text(
            self._t("Your content, always one click away."),
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.footer_country_label = ft.Text(
            self._t("Country: checking..."),
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        page.add(
            ft.Column(
                [
                    ft.Row(
                        [
                            self.nav_rail,
                            ft.VerticalDivider(width=1, thickness=1, opacity=0.15),
                            self.main_container,
                        ],
                        expand=True,
                        spacing=0,
                    ),
                    self.stop_download_area,
                    ft.Column(
                        [
                            ft.Divider(height=1, thickness=1, opacity=0.15),
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Text(
                                            self._t("DASH.IO"),
                                            size=12,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.INDIGO_300,
                                        ),
                                        self.footer_tagline,
                                        self.footer_country_label,
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                padding=ft.Padding.symmetric(
                                    horizontal=24,
                                    vertical=10,
                                ),
                            ),
                        ],
                        spacing=0,
                    ),
                ],
                expand=True,
                spacing=0,
            )
        )
        self.show_video_lab()
        self._apply_interface_language()
        if get_country_analytics_enabled():
            self._schedule_country_analytics()
        self._schedule_auth_restore()
        if not get_country_analytics_enabled():
            self._schedule_footer_country_lookup()

    def _open_account_settings(self, _event=None):
        self.nav_rail.selected_index = 4
        self.show_settings()

    def _apply_interface_language(self):
        self._translate_control(self.main_container.content)
        self._translate_control(self.page.appbar)
        self._translate_control(self.nav_rail)
        self._translate_control(self.stop_download_area)
        self._translate_control(self.footer_tagline)
        self._translate_control(self.footer_country_label)
        self.page.update()

    def change_language(self, language: str):
        previous_language = self.language
        self.language = language
        try:
            save_language(language)
        except (OSError, ValueError) as exc:
            self.language = previous_language
            if hasattr(self, "language_dropdown"):
                self.language_dropdown.value = previous_language
            self._show_message(
                self._t(f"Could not save language preference: {exc}"),
                ft.Colors.RED_200,
            )
            return
        self._apply_interface_language()

    def stop_active_download(self, _e=None):
        if not (self.download_running or self.torrent_download_running):
            return
        self.download_cancel_event.set()
        self.stop_download_button.disabled = True
        self._show_message(self._t("Stopping download..."), ft.Colors.RED_200)
        self.page.update()

    def _set_stop_download_visible(self, visible: bool):
        self.stop_download_area.visible = visible
        self.stop_download_button.visible = visible
        self.stop_download_button.disabled = not visible

    def toggle_theme(self):
        if self.page.theme_mode == ft.ThemeMode.DARK:
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.theme_icon_btn.icon = ft.Icons.LIGHT_MODE
        else:
            self.page.theme_mode = ft.ThemeMode.DARK
            self.theme_icon_btn.icon = ft.Icons.DARK_MODE
        self.page.update()

    def on_nav_change(self, e):
        views = [
            self.show_video_lab,
            self.show_lamovie,
            self.show_markdown_export,
            self.show_torrent,
            self.show_settings,
        ]
        selected_index = e.control.selected_index
        if 0 <= selected_index < len(views):
            views[selected_index]()


def main(page: ft.Page):
    YouTuberDownloaderApp(page)
