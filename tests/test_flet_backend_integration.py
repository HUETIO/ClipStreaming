import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import flet as ft
from yt_dlp.utils import DownloadCancelled

import abrir_torrent_descargar
from app.infrastructure.video.video_lab import VideoLab
from app.config import get_language, save_language
from app.presentation.app import YouTuberDownloaderApp


class VideoLabBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.video_lab = VideoLab(self.temp_dir.name)

    @patch("app.infrastructure.video.video_lab.yt_dlp.YoutubeDL")
    def test_video_download_calls_ytdlp_and_creates_output_directory(self, youtube_dl):
        downloader = MagicMock()
        downloader.__enter__.return_value = downloader
        downloader.extract_info.return_value = {"id": "sample"}
        youtube_dl.return_value = downloader

        result = self.video_lab.download_video(
            "https://youtube.com/watch?v=sample",
            output_dir=self.temp_dir.name,
        )

        self.assertEqual(result, str(Path(self.temp_dir.name) / "video"))
        downloader.extract_info.assert_called_once_with(
            "https://youtube.com/watch?v=sample",
            download=True,
        )

    @patch("app.infrastructure.video.video_lab.yt_dlp.YoutubeDL")
    def test_combined_download_uses_video_and_audio_backends(self, youtube_dl):
        downloader = MagicMock()
        downloader.__enter__.return_value = downloader
        downloader.extract_info.return_value = {"id": "sample"}
        youtube_dl.return_value = downloader

        result = self.video_lab.download_video(
            "https://youtube.com/watch?v=sample",
            download_type="both",
            output_dir=self.temp_dir.name,
        )

        self.assertIn("MP4:", result)
        self.assertIn("MP3:", result)
        self.assertEqual(downloader.extract_info.call_count, 2)

    def test_video_lab_view_dispatches_download_to_backend(self):
        app = object.__new__(YouTuberDownloaderApp)
        app.video_lab = MagicMock()
        app.download_cancel_event = threading.Event()
        app.video_lab.normalize_url.return_value = (
            "https://youtube.com/watch?v=sample",
            "youtube",
        )
        app.video_lab.download_video.return_value = str(
            Path(self.temp_dir.name) / "video"
        )
        app.video_status = ft.Text()
        app.page = cast(ft.Page, SimpleNamespace(update=Mock()))
        options = {
            "quality": "720",
            "output_format": "mp4",
            "download_type": "video",
            "output_dir": self.temp_dir.name,
            "skip_existing": True,
            "cookies_file": None,
            "browser": None,
        }

        result = asyncio.run(
            app._download_one(
                "https://youtube.com/watch?v=sample",
                is_playlist=False,
                options=options,
            )
        )

        self.assertTrue(result.endswith("video"))
        app.video_lab.download_video.assert_called_once()
        self.assertEqual(
            app.video_lab.download_video.call_args.args[:3],
            ("https://youtube.com/watch?v=sample", "720", "mp4"),
        )

    def test_video_download_cancellation_stops_the_backend(self):
        app = object.__new__(YouTuberDownloaderApp)
        app.video_lab = MagicMock()
        app.video_lab.normalize_url.return_value = (
            "https://youtube.com/watch?v=sample",
            "youtube",
        )
        app.video_lab.download_video.side_effect = (
            lambda *args, **kwargs: kwargs["progress_hook"](
                {"status": "downloading"}
            )
        )
        app.download_cancel_event = threading.Event()
        app.download_cancel_event.set()
        app.video_status = ft.Text()
        app.page = cast(ft.Page, SimpleNamespace(update=Mock()))
        options = {
            "quality": "720",
            "output_format": "mp4",
            "download_type": "video",
            "output_dir": "downloads",
            "skip_existing": True,
            "cookies_file": None,
            "browser": None,
        }

        with self.assertRaises(DownloadCancelled):
            asyncio.run(
                app._download_one(
                    "https://youtube.com/watch?v=sample",
                    is_playlist=False,
                    options=options,
                )
            )


class ExternalToolIntegrationTests(unittest.TestCase):
    def make_app(self):
        app = object.__new__(YouTuberDownloaderApp)
        app.page = cast(ft.Page, SimpleNamespace(update=Mock()))
        app.external_task_running = False
        app.torrent_download_running = False
        app.download_cancel_event = threading.Event()
        app.stop_download_button = ft.FilledButton("STOP", disabled=True)
        app.stop_download_area = ft.Container(visible=False)
        return app

    @patch("app.presentation.external_tools_view.lamovie.resolve_lamovie")
    def test_lamovie_screen_calls_existing_resolver(self, resolve_lamovie):
        resolve_lamovie.return_value = {
            "title": "Sample",
            "embeds": [],
            "downloads": [],
        }
        app = self.make_app()
        app.lamovie_url_field = ft.TextField(value="https://lamovie.org/peliculas/sample/")
        app.lamovie_status = ft.Text()
        app.lamovie_result = ft.Text()
        app.lamovie_button = ft.FilledButton("Resolve")

        asyncio.run(app._resolve_lamovie())

        resolve_lamovie.assert_called_once_with(
            "https://lamovie.org/peliculas/sample/"
        )
        self.assertIn("Sample", app.lamovie_result.value)
        self.assertIn("Sample", app.lamovie_status.value)

    @patch("app.presentation.external_tools_view.downloads_dir")
    @patch("app.presentation.external_tools_view.markdown_utils.generate_markdown")
    def test_markdown_screen_calls_generator_and_saves_to_selected_folder(
        self,
        generate_markdown,
        configured_downloads,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            configured_downloads.return_value = temp_dir
            generate_markdown.return_value = "# Sample page"
            app = self.make_app()
            app.markdown_url_field = ft.TextField(value="https://example.com/article")
            app.markdown_output_field = ft.TextField(value=temp_dir)
            app.markdown_status = ft.Text()
            app.markdown_preview = ft.Text()
            app.markdown_button = ft.FilledButton("Convert")

            asyncio.run(app._generate_markdown())

            expected_path = str(Path(temp_dir) / "article.md")
            generate_markdown.assert_called_once_with(
                "https://example.com/article",
                expected_path,
            )
            self.assertEqual(app.markdown_preview.value, "# Sample page")
            self.assertIn(expected_path, app.markdown_status.value)

    @patch("app.presentation.external_tools_view.abrir_torrent_descargar.descargar")
    @patch("app.presentation.external_tools_view.abrir_torrent_descargar.is_available")
    def test_torrent_screen_disables_action_when_libtorrent_is_missing(
        self,
        is_available,
        download_torrent,
    ):
        is_available.return_value = False
        app = self.make_app()
        app.main_container = ft.Container()

        app.show_torrent()
        app.torrent_magnet_field.value = "magnet:?xt=urn:btih:sample"
        asyncio.run(app._download_torrent())

        self.assertTrue(app.torrent_button.disabled)
        self.assertIn("no disponibles", app.torrent_status.value)
        download_torrent.assert_not_called()

    @patch("app.presentation.external_tools_view.downloads_dir")
    @patch("app.presentation.external_tools_view.abrir_torrent_descargar.descargar")
    @patch("app.presentation.external_tools_view.abrir_torrent_descargar.is_available")
    def test_torrent_progress_callback_queues_multiple_values_as_one_event(
        self,
        is_available,
        download_torrent,
        configured_downloads,
    ):
        is_available.return_value = True
        configured_downloads.return_value = "downloads"

        def download_with_progress(
            _magnet,
            _output_dir,
            progress_callback,
            cancel_event,
        ):
            progress_callback({"type": "log", "message": "Tracker conectado"})
            progress_callback(
                {
                    "type": "progress",
                    "stage": "downloading",
                    "progress": 0.5,
                    "download_rate": 1024,
                    "upload_rate": 256,
                    "peers": 3,
                    "seeds": 2,
                    "connections": 3,
                    "downloaded": 512 * 1024,
                    "total_size": 1024 * 1024,
                    "elapsed": 5,
                }
            )
            return {
                "completed": True,
                "name": "sample.mkv",
                "path": "downloads/torrent/sample.mkv",
            }

        download_torrent.side_effect = download_with_progress
        app = self.make_app()
        app.torrent_magnet_field = ft.TextField(
            value="magnet:?xt=urn:btih:sample"
        )
        app.torrent_button = ft.FilledButton("Download")
        app.torrent_progress = ft.ProgressBar()
        app.torrent_progress_label = ft.Text()
        app.torrent_details = ft.Text()
        app.torrent_status = ft.Text()
        app.torrent_log_lines = []
        app.torrent_logs = ft.TextField()

        asyncio.run(app._download_torrent())

        self.assertIn("Descarga completada", app.torrent_status.value)
        self.assertIn("sample.mkv", app.torrent_status.value)
        self.assertEqual(app.torrent_progress.value, 1)
        self.assertEqual(app.torrent_progress_label.value, "100.0%")
        self.assertIn("Tracker conectado", app.torrent_logs.value)
        self.assertIn("0.5 / 1.0 MB", app.torrent_details.value)
        download_torrent.assert_called_once()

    @patch("app.presentation.external_tools_view.downloads_dir")
    @patch("app.presentation.external_tools_view.abrir_torrent_descargar.descargar")
    @patch("app.presentation.external_tools_view.abrir_torrent_descargar.is_available")
    def test_torrent_screen_passes_selected_torrent_file_to_downloader(
        self,
        is_available,
        download_torrent,
        configured_downloads,
    ):
        is_available.return_value = True
        configured_downloads.return_value = "downloads"
        download_torrent.return_value = {
            "completed": True,
            "name": "sample.mkv",
            "path": "downloads/torrent/sample.mkv",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            torrent_path = Path(temp_dir) / "sample.torrent"
            torrent_path.write_bytes(b"torrent fixture")
            app = self.make_app()
            app.torrent_magnet_field = ft.TextField(value=str(torrent_path))
            app.torrent_button = ft.FilledButton("Download")
            app.torrent_progress = ft.ProgressBar()
            app.torrent_progress_label = ft.Text()
            app.torrent_details = ft.Text()
            app.torrent_status = ft.Text()
            app.torrent_log_lines = []
            app.torrent_logs = ft.TextField()

            asyncio.run(app._download_torrent())

        self.assertEqual(download_torrent.call_args.args[0], str(torrent_path))
        self.assertEqual(download_torrent.call_args.args[1], str(Path("downloads") / "torrent"))
        self.assertIn("Descarga completada", app.torrent_status.value)

    def test_torrent_file_picker_populates_source_field(self):
        app = self.make_app()
        selected_file = SimpleNamespace(path="C:\\torrents\\sample.torrent")
        pick_files = AsyncMock(return_value=[selected_file])
        app.file_picker = cast(
            ft.FilePicker,
            SimpleNamespace(pick_files=pick_files),
        )
        app.torrent_magnet_field = ft.TextField()

        asyncio.run(app._choose_torrent_file())

        self.assertEqual(
            app.torrent_magnet_field.value,
            "C:\\torrents\\sample.torrent",
        )
        pick_files.assert_awaited_once_with(
            dialog_title="Selecciona un archivo .torrent",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["torrent"],
            allow_multiple=False,
        )

    def test_torrent_magnet_is_resumed_and_reports_completion(self):
        mock_lt = MagicMock()
        mock_lt.torrent_flags.paused = 1
        mock_lt.torrent_flags.auto_managed = 2
        params = SimpleNamespace(trackers=[], flags=1, save_path="")
        mock_lt.parse_magnet_uri.return_value = params
        session = MagicMock()
        mock_lt.session.return_value = session
        handle = MagicMock()
        session.add_torrent.return_value = handle
        status = MagicMock()
        status.has_metadata = True
        status.progress = 1.0
        status.is_seeding = True
        status.is_finished = True
        status.errc.value.return_value = 0
        status.download_rate = 0
        status.upload_rate = 0
        status.num_peers = 1
        status.num_seeds = 1
        status.num_connections = 1
        status.total_done = 1024
        handle.status.return_value = status
        handle.torrent_file.return_value.name.return_value = "sample.mkv"
        handle.torrent_file.return_value.total_size.return_value = 1024
        events = []

        with tempfile.TemporaryDirectory() as output_dir:
            with patch.object(abrir_torrent_descargar, "lt", mock_lt):
                result = abrir_torrent_descargar.descargar(
                    "magnet:?xt=urn:btih:sample",
                    output_dir,
                    progress_callback=events.append,
                )

        self.assertFalse(params.flags & mock_lt.torrent_flags.paused)
        self.assertTrue(params.flags & mock_lt.torrent_flags.auto_managed)
        handle.resume.assert_called_once()
        self.assertTrue(result["completed"])
        self.assertIn("downloading", [event.get("stage") for event in events])

    @patch("app.presentation.external_tools_view.abrir_torrent_descargar.descargar")
    @patch("app.presentation.external_tools_view.abrir_torrent_descargar.is_available")
    def test_torrent_metadata_failure_stops_progress_indicator_and_logs_error(
        self,
        is_available,
        download_torrent,
    ):
        is_available.return_value = True

        def fail_before_metadata(
            _source,
            _output_dir,
            progress_callback,
            cancel_event,
        ):
            progress_callback(
                {
                    "type": "progress",
                    "stage": "metadata",
                    "progress": None,
                    "download_rate": 0,
                    "upload_rate": 0,
                    "peers": 0,
                    "seeds": 0,
                    "connections": 0,
                    "downloaded": 0,
                    "total_size": 0,
                    "elapsed": 10,
                }
            )
            raise TimeoutError("No se obtuvieron metadatos")

        download_torrent.side_effect = fail_before_metadata
        app = self.make_app()
        app.torrent_magnet_field = ft.TextField(
            value="magnet:?xt=urn:btih:sample"
        )
        app.torrent_button = ft.FilledButton("Download")
        app.torrent_progress = ft.ProgressBar()
        app.torrent_progress_label = ft.Text()
        app.torrent_details = ft.Text()
        app.torrent_status = ft.Text()
        app.torrent_log_lines = []
        app.torrent_logs = ft.TextField()

        asyncio.run(app._download_torrent())

        self.assertEqual(app.torrent_progress.value, 0)
        self.assertEqual(app.torrent_progress_label.value, "No completada")
        self.assertIn("No se obtuvieron metadatos", app.torrent_status.value)
        self.assertIn("Error:", app.torrent_logs.value)


class AppNavigationTests(unittest.TestCase):
    def test_language_preference_is_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            preference_file = Path(temp_dir) / "settings.json"
            with patch("app.config.USER_SETTINGS_PATH", preference_file):
                save_language("en-US")
                self.assertEqual(get_language(), "en-US")
                save_language("es")
                self.assertEqual(get_language(), "es")

    @patch("app.presentation.app.save_language")
    @patch("app.presentation.app.get_language", return_value="es")
    def test_language_selection_translates_interface_and_persists(
        self, _get_language, save_language
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
        self.assertEqual(app.video_download_buttons[0].content, "Descargar video")
        self.assertEqual(app.quality_drop.options[0].text, "Mejor")
        self.assertEqual(app.stop_download_button.content, "DETENER")
        app.on_nav_change(SimpleNamespace(control=SimpleNamespace(selected_index=4)))
        app._on_language_select(SimpleNamespace(control=SimpleNamespace(value="en-US")))

        self.assertEqual(app.language, "en-US")
        self.assertEqual(app.nav_rail.destinations[0].label, "Video Lab")
        self.assertEqual(app.language_dropdown.options[0].text, "Spanish")
        self.assertEqual(app.language_dropdown.label, "Language")
        self.assertEqual(app.folder_field.label, "Download folder")
        self.assertEqual(app.theme_switch.label, "Dark mode")
        self.assertEqual(app.footer_tagline.value, "Your content, always one click away.")
        self.assertEqual(app.stop_download_button.content, "STOP")
        save_language.assert_called_once_with("en-US")

        app.on_nav_change(SimpleNamespace(control=SimpleNamespace(selected_index=0)))
        self.assertEqual(app.video_download_buttons[0].content, "Download video")
        self.assertEqual(app.queue_add_button.content, "Add to queue")
        self.assertEqual(app.quality_drop.options[0].text, "Best")
        app.on_nav_change(SimpleNamespace(control=SimpleNamespace(selected_index=1)))
        self.assertEqual(app.lamovie_button.content, "Resolve links")
        self.assertEqual(app.lamovie_url_field.label, "Lamovie URL")
        app.on_nav_change(SimpleNamespace(control=SimpleNamespace(selected_index=2)))
        self.assertEqual(app.markdown_button.content, "Convert and save")
        app.on_nav_change(SimpleNamespace(control=SimpleNamespace(selected_index=3)))
        self.assertEqual(app.torrent_button.content, "Start download")
        self.assertEqual(app.torrent_file_button.content, "Choose .torrent file")

        app.on_nav_change(SimpleNamespace(control=SimpleNamespace(selected_index=4)))
        app._on_language_select(SimpleNamespace(control=SimpleNamespace(value="es")))
        self.assertEqual(app.nav_rail.destinations[0].label, "Laboratorio de video")
        self.assertEqual(app.language_dropdown.options[1].text, "Inglés (Estados Unidos)")
        self.assertEqual(app.folder_field.label, "Carpeta de descargas")
        self.assertEqual(app.theme_switch.label, "Modo oscuro")
        self.assertEqual(app.footer_tagline.value, "Tu contenido, siempre a un clic.")
        self.assertEqual(app.stop_download_button.content, "DETENER")
        app.on_nav_change(SimpleNamespace(control=SimpleNamespace(selected_index=0)))
        self.assertEqual(app.video_download_buttons[0].content, "Descargar video")
        self.assertEqual(app.queue_add_button.content, "Añadir a la cola")
        self.assertEqual(app.quality_drop.options[0].text, "Mejor")
        app.on_nav_change(SimpleNamespace(control=SimpleNamespace(selected_index=1)))
        self.assertEqual(app.lamovie_button.content, "Resolver enlaces")
        app.on_nav_change(SimpleNamespace(control=SimpleNamespace(selected_index=2)))
        self.assertEqual(app.markdown_button.content, "Convertir y guardar")
        app.on_nav_change(SimpleNamespace(control=SimpleNamespace(selected_index=3)))
        self.assertEqual(app.torrent_button.content, "Iniciar descarga")
        self.assertEqual(app.torrent_file_button.content, "Elegir archivo .torrent")

    def test_stop_button_requests_cancellation_of_active_download(self):
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
        app.download_running = True
        app.stop_download_button.disabled = False

        app.stop_active_download()

        self.assertTrue(app.download_cancel_event.is_set())
        self.assertTrue(app.stop_download_button.disabled)

    def test_stop_button_visibility_tracks_active_downloads(self):
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
        self.assertFalse(app.stop_download_button.visible)
        self.assertFalse(app.stop_download_area.visible)

        app._set_stop_download_visible(True)
        self.assertTrue(app.stop_download_button.visible)
        self.assertTrue(app.stop_download_area.visible)
        self.assertFalse(app.stop_download_button.disabled)

        app._set_stop_download_visible(False)
        self.assertFalse(app.stop_download_button.visible)
        self.assertFalse(app.stop_download_area.visible)
        self.assertTrue(app.stop_download_button.disabled)

    def test_download_settings_uses_unboxed_layout_and_keeps_download_controls(self):
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

        self.assertIsInstance(app.download_settings_panel, ft.Column)
        self.assertIsInstance(app.output_dir_field, ft.Text)
        self.assertTrue(app.output_dir_field.value.startswith("Destino: "))
        self.assertEqual(app.cookies_file_field.height, 56)
        self.assertNotEqual(app.video_url_field.expand, True)
        self.assertIsNone(getattr(app.download_settings_panel, "bgcolor", None))
        self.assertEqual(app.main_container.bgcolor, ft.Colors.SURFACE)
        content_row = app.main_container.content.controls[1]
        self.assertIsInstance(content_row, ft.Row)
        self.assertEqual(
            [column.expand for column in content_row.controls],
            [7, 5],
        )
        settings_column = next(
            control
            for control in content_row.controls
            if isinstance(control, ft.Container)
            and control.content is app.download_settings_panel
        )
        self.assertEqual(settings_column.bgcolor, ft.Colors.TRANSPARENT)
        settings_heading = app.download_settings_panel.controls[0]
        self.assertIsInstance(settings_heading, ft.Column)
        self.assertFalse(
            any(isinstance(control, ft.Container) for control in settings_heading.controls)
        )
        self.assertIn(app.video_url_field, app.download_settings_panel.controls)
        output_row = next(
            control
            for control in app.download_settings_panel.controls
            if isinstance(control, ft.Row)
            and app.output_dir_field in control.controls
        )
        self.assertIsNotNone(output_row)
        self.assertIn(app.skip_existing_checkbox, app.download_settings_panel.controls)

    def test_text_inputs_do_not_expand_vertically_inside_scrollable_screens(self):
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

        self.assertIsNone(app.video_url_field.expand)
        self.assertIsNone(app.queue_input.expand)
        self.assertIsNone(app.cookies_file_field.expand)
        app.show_lamovie()
        self.assertIsNone(app.lamovie_url_field.expand)
        app.show_markdown_export()
        self.assertIsNone(app.markdown_url_field.expand)
        app.show_torrent()
        self.assertIsNone(app.torrent_magnet_field.expand)

    def test_all_backend_screens_are_reachable_from_navigation(self):
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
        self.assertEqual(page.title, "Clipstream")
        footer = page.add.call_args.args[0].controls[2].controls[1].content
        self.assertEqual(
            [control.value for control in footer.controls],
            [
                "DASH.IO",
                "Tu contenido, siempre a un clic.",
                "País: consultando...",
            ],
        )
        for index in range(5):
            app.on_nav_change(
                SimpleNamespace(control=SimpleNamespace(selected_index=index))
            )

        self.assertEqual(len(app.nav_rail.destinations), 5)
        self.assertIsInstance(app.video_lab, VideoLab)
        self.assertIsNotNone(page.appbar)
        self.assertNotIn(app.stop_download_button, page.appbar.actions)
        self.assertFalse(app.stop_download_button.visible)
        self.assertFalse(app.stop_download_area.visible)
        self.assertEqual(app.theme_switch.value, page.theme_mode == ft.ThemeMode.DARK)

    def test_theme_switch_updates_theme_and_indicator(self):
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
        self.assertEqual(page.bgcolor, ft.Colors.SURFACE)
        self.assertEqual(app.main_container.bgcolor, ft.Colors.SURFACE)

        app._on_theme_switch()
        self.assertEqual(page.theme_mode, ft.ThemeMode.LIGHT)
        self.assertEqual(page.bgcolor, ft.Colors.SURFACE)
        self.assertEqual(app.main_container.bgcolor, ft.Colors.SURFACE)
        self.assertFalse(app.theme_switch.value)
        self.assertEqual(app.theme_label.value, "Tema actual: Claro")

        app._on_theme_switch()
        self.assertEqual(page.theme_mode, ft.ThemeMode.DARK)
        self.assertEqual(page.bgcolor, ft.Colors.SURFACE)
        self.assertEqual(app.main_container.bgcolor, ft.Colors.SURFACE)

    def test_settings_folder_selection_updates_video_lab_default(self):
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
        app.file_picker.get_directory_path = AsyncMock(
            return_value="D:\\media\\saved"
        )

        asyncio.run(app._on_browse_folder())

        self.assertEqual(app.output_folder, "D:\\media\\saved")
        self.assertEqual(app.folder_field.value, "D:\\media\\saved")
        app.show_video_lab()
        self.assertEqual(
            app.output_dir_field.value,
            "Destino: D:\\media\\saved",
        )

    def test_video_queue_renders_active_download(self):
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
        app.download_queue.append(
            {
                "id": 1,
                "url": "https://example.com/video",
                "status": "Downloading",
                "progress": 0.5,
                "message": "video.mp4",
            }
        )

        app._render_download_queue()

        self.assertTrue(app.queue_panel.visible)
        self.assertEqual(len(app.queue_list.controls), 1)


if __name__ == "__main__":
    unittest.main()
