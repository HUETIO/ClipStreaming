from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import flet as ft

import abrir_torrent_descargar
import lamovie
import markdown_utils
from app.config import downloads_dir
from app.presentation.components import PresentationComponents


class ExternalToolsView(PresentationComponents):
    page: ft.Page
    file_picker: ft.FilePicker
    external_task_running: bool

    def _tool_page(self, title: str, subtitle: str, icon, controls):
        self._render_page(
            ft.Column(
                [
                    self._section_heading(title, subtitle, icon),
                    self._surface(
                        ft.Column(controls, spacing=16),
                        padding=24,
                    ),
                ],
                spacing=24,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            )
        )

    def show_lamovie(self):
        self.lamovie_url_field = ft.TextField(
            label="Lamovie URL",
            hint_text="https://lamovie.org/peliculas/...",
        )
        self.lamovie_status = ft.Text("Enter a URL to resolve its links.")
        self.lamovie_result = ft.Text(selectable=True, font_family="Consolas")
        self.lamovie_button = ft.FilledButton(
            "Resolve links",
            icon=ft.Icons.SEARCH,
            on_click=self._resolve_lamovie,
        )
        self._tool_page(
            "Resolve Lamovie",
            "Look up title details and its playback and download links.",
            ft.Icons.MOVIE,
            [
                self.lamovie_url_field,
                self.lamovie_button,
                self.lamovie_status,
                self.lamovie_result,
            ],
        )

    async def _resolve_lamovie(self, _e=None):
        url = (self.lamovie_url_field.value or "").strip()
        if not url:
            self.lamovie_status.value = self._t("Enter the Lamovie URL.")
            self.page.update()
            return
        if self.external_task_running:
            return

        self.external_task_running = True
        self.lamovie_button.disabled = True
        self.lamovie_status.value = self._t("Looking up Lamovie...")
        self.lamovie_result.value = ""
        self.page.update()
        try:
            result = await asyncio.to_thread(lamovie.resolve_lamovie, url)
        except Exception as exc:
            self.lamovie_status.value = self._t(f"Could not resolve link: {exc}")
        else:
            self.lamovie_status.value = (
                self._t(f"Result: {result.get('title') or result.get('slug') or url}")
            )
            self.lamovie_result.value = json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        finally:
            self.external_task_running = False
            self.lamovie_button.disabled = False
            self.page.update()

    def show_markdown_export(self):
        self.markdown_url_field = ft.TextField(
            label="Page URL",
            hint_text="https://example.com/article",
        )
        self.markdown_output_field = ft.TextField(
            label="Output folder",
            value=str(Path(downloads_dir()) / "markdown"),
            read_only=True,
            expand=True,
        )
        self.markdown_status = ft.Text("The content will be saved as a .md file.")
        self.markdown_preview = ft.Text(
            selectable=True,
            max_lines=18,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.markdown_button = ft.FilledButton(
            "Convert and save",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._generate_markdown,
        )
        self._tool_page(
            "Web to Markdown",
            "Extract metadata and convert a web page to Markdown.",
            ft.Icons.DESCRIPTION,
            [
                self.markdown_url_field,
                ft.Row(
                    [
                        self.markdown_output_field,
                        ft.OutlinedButton(
                            "Change folder",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=self._choose_markdown_directory,
                        ),
                    ],
                    spacing=12,
                ),
                self.markdown_button,
                self.markdown_status,
                self.markdown_preview,
            ],
        )

    async def _choose_markdown_directory(self, _e=None):
        selected = await self.file_picker.get_directory_path(
            dialog_title=self._t("Select the Markdown folder"),
            initial_directory=self.markdown_output_field.value,
        )
        if selected:
            self.markdown_output_field.value = selected
            self.page.update()

    async def _generate_markdown(self, _e=None):
        url = (self.markdown_url_field.value or "").strip()
        if not url.startswith(("http://", "https://")):
            self.markdown_status.value = self._t(
                "Enter a valid http:// or https:// URL."
            )
            self.page.update()
            return
        if self.external_task_running:
            return

        output_dir = Path(
            self.markdown_output_field.value or Path(downloads_dir()) / "markdown"
        )
        output_path = output_dir / f"{markdown_utils.slug_from_url(url)}.md"
        self.external_task_running = True
        self.markdown_button.disabled = True
        self.markdown_status.value = self._t("Downloading and converting the page...")
        self.markdown_preview.value = ""
        self.page.update()
        try:
            markdown_text = await asyncio.to_thread(
                markdown_utils.generate_markdown,
                url,
                str(output_path),
            )
        except Exception as exc:
            self.markdown_status.value = self._t(f"Could not create Markdown: {exc}")
        else:
            self.markdown_status.value = self._t(f"File saved: {output_path}")
            self.markdown_preview.value = markdown_text[:6000]
        finally:
            self.external_task_running = False
            self.markdown_button.disabled = False
            self.page.update()

    def show_torrent(self):
        self.torrent_magnet_field = ft.TextField(
            label="Magnet link",
            hint_text="magnet:?xt=urn:btih:...",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )
        self.torrent_progress = ft.ProgressBar(visible=False)
        self.torrent_progress_label = ft.Text("0.0%")
        self.torrent_details = ft.Text("")
        self.torrent_log_lines: list[str] = []
        self.torrent_logs = ft.TextField(
            label="Download log",
            value="",
            multiline=True,
            read_only=True,
            min_lines=6,
            max_lines=10,
            text_size=12,
        )
        self.torrent_status = ft.Text(
            "Ready to download."
            if abrir_torrent_descargar.is_available()
            else "Torrent downloads unavailable: install libtorrent to enable them."
        )
        self.torrent_button = ft.FilledButton(
            "Start download",
            icon=ft.Icons.DOWNLOAD,
            disabled=not abrir_torrent_descargar.is_available(),
            on_click=self._download_torrent,
        )
        self.torrent_file_button = ft.OutlinedButton(
            "Choose .torrent file",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._choose_torrent_file,
        )
        self._tool_page(
            "Torrent downloads",
            "Paste a magnet link or choose a .torrent file.",
            ft.Icons.DOWNLOAD_FOR_OFFLINE,
            [
                self.torrent_magnet_field,
                self.torrent_file_button,
                ft.Text(self._t(f"Destination: {Path(downloads_dir()) / 'torrent'}")),
                self.torrent_button,
                self.torrent_progress,
                self.torrent_progress_label,
                self.torrent_details,
                self.torrent_status,
                self.torrent_logs,
            ],
        )

    async def _choose_torrent_file(self, _e=None):
        files = await self.file_picker.pick_files(
            dialog_title=self._t("Select a .torrent file"),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["torrent"],
            allow_multiple=False,
        )
        if files and files[0].path:
            self.torrent_magnet_field.value = files[0].path
            self.page.update()

    async def _download_torrent(self, _e=None):
        source = (self.torrent_magnet_field.value or "").strip()
        if not source or (
            not abrir_torrent_descargar.es_magnet(source)
            and not Path(source.strip('"')).is_file()
        ):
            self.torrent_status.value = self._t(
                "Paste a valid magnet link or choose an existing .torrent file."
            )
            self.page.update()
            return
        if self.external_task_running:
            return
        if not abrir_torrent_descargar.is_available():
            self.torrent_status.value = self._t(
                "Torrent downloads unavailable: install libtorrent and restart the app."
            )
            self.page.update()
            return

        progress_events: Queue[dict[str, Any]] = Queue()
        output_dir = str(Path(downloads_dir()) / "torrent")
        self.external_task_running = True
        self.torrent_download_running = True
        self.download_cancel_event.clear()
        self._set_stop_download_visible(True)
        self.torrent_button.disabled = True
        self.torrent_progress.visible = True
        self.torrent_progress.value = 0
        self.torrent_progress_label.value = "0.0%"
        self.torrent_details.value = ""
        self.torrent_log_lines = []
        self.torrent_logs.value = ""
        self.torrent_status.value = self._t("Connecting to the torrent network...")
        self.page.update()

        def on_torrent_progress(event: dict[str, Any]):
            progress_events.put(event)

        download_task = asyncio.create_task(
            asyncio.to_thread(
                abrir_torrent_descargar.descargar,
                source,
                output_dir,
                progress_callback=on_torrent_progress,
                cancel_event=self.download_cancel_event,
            )
        )
        try:
            while not download_task.done():
                self._update_torrent_progress(progress_events)
                await asyncio.sleep(0.3)
            self._update_torrent_progress(progress_events)
            result = await download_task
        except Exception as exc:
            if self.download_cancel_event.is_set():
                self.torrent_status.value = self._t("Download stopped.")
                self.torrent_progress_label.value = self._t("Stopped")
                self._append_torrent_log("Download stopped by user.")
            else:
                self.torrent_status.value = self._t(
                    f"Could not download torrent: {exc}"
                )
                self.torrent_progress.value = 0
                self.torrent_progress_label.value = self._t("Incomplete")
                self._append_torrent_log(f"Error: {exc}")
        else:
            completed = result["completed"]
            self.torrent_progress.value = 1 if completed else self.torrent_progress.value
            if completed:
                self.torrent_progress_label.value = "100.0%"
            state = self._t("completed" if result["completed"] else "incomplete")
            self.torrent_status.value = (
                f"{self._t('Download ')}{state}: {result['name']} — {result['path']}"
            )
            self._append_torrent_log(self.torrent_status.value)
        finally:
            self.external_task_running = False
            self.torrent_download_running = False
            self._set_stop_download_visible(False)
            self.torrent_button.disabled = not abrir_torrent_descargar.is_available()
            self.page.update()

    def _append_torrent_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.torrent_log_lines.append(f"[{timestamp}] {self._t(message)}")
        self.torrent_log_lines = self.torrent_log_lines[-100:]
        self.torrent_logs.value = "\n".join(self.torrent_log_lines)

    def _update_torrent_progress(self, progress_events: Queue[dict[str, Any]]):
        changed = False
        while True:
            try:
                event = progress_events.get_nowait()
            except Empty:
                break
            changed = True
            if event.get("type") == "log":
                self._append_torrent_log(event["message"])
                continue

            elapsed = event["elapsed"]
            peers = event["peers"]
            seeds = event["seeds"]
            connections = event["connections"]
            rate = event["download_rate"]
            upload_rate = event["upload_rate"]
            if event["stage"] == "metadata":
                self.torrent_progress.value = None
                self.torrent_progress_label.value = self._t("Waiting for metadata")
                self.torrent_status.value = self._t(
                    "Looking for peers to retrieve metadata..."
                )
                self.torrent_details.value = (
                    f"{peers} {self._t('peers')} · "
                    f"{seeds} {self._t('seeds')} · {connections}"
                    f" {self._t('connections')} · {elapsed:.0f}"
                    f"{self._t(' s elapsed')}"
                )
                continue

            progress = event["progress"]
            downloaded = event["downloaded"]
            total_size = event["total_size"]
            self.torrent_progress.value = progress
            self.torrent_progress_label.value = f"{progress * 100:.1f}%"
            self.torrent_status.value = (
                f"{self._t('Downloading · ')}{rate / 1024:.0f} KB/s · "
                f"{peers} {self._t('peers')} · {seeds} {self._t('seeds')}"
            )
            if rate > 0 and total_size > downloaded:
                eta = (total_size - downloaded) / rate
                eta_value = eta / 60 if eta >= 60 else eta
                eta_unit = " min remaining" if eta >= 60 else " s remaining"
                eta_text = f"{eta_value:.0f}{self._t(eta_unit)}"
            else:
                eta_text = self._t("ETA unavailable")
            self.torrent_details.value = (
                f"{downloaded / (1024 ** 2):.1f} / {total_size / (1024 ** 2):.1f} MB · "
                f"↑ {upload_rate / 1024:.0f} KB/s · {connections} "
                f"{self._t('connections')} · {elapsed:.0f}"
                f"{self._t(' s elapsed')} · {eta_text}"
            )
        if changed:
            self.page.update()
