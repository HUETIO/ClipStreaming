from __future__ import annotations

import asyncio
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import flet as ft
from yt_dlp.utils import DownloadCancelled

from app.config import downloads_dir


class VideoLabView:
    def show_video_lab(self):
        self.video_url_field = ft.TextField(
            label="Video or playlist URL",
            hint_text="https://youtube.com/... or https://vimeo.com/...",
        )
        self.download_type_drop = ft.Dropdown(
            label="Media type",
            options=[
                ft.dropdown.Option("both", "Video (MP4) + Audio (MP3)"),
                ft.dropdown.Option("video", "Video only (MP4/MKV)"),
                ft.dropdown.Option("mp3", "Audio only (MP3)"),
            ],
            value="video",
            width=190,
            on_select=self._on_download_type_change,
        )
        self.quality_drop = ft.Dropdown(
            label="Quality",
            options=[
                ft.dropdown.Option("best", "Best"),
                ft.dropdown.Option("1080"),
                ft.dropdown.Option("720"),
                ft.dropdown.Option("480"),
                ft.dropdown.Option("360"),
                ft.dropdown.Option("worst", "Worst"),
            ],
            value="best",
            width=140,
        )
        self.format_drop = ft.Dropdown(
            label="Container",
            options=[ft.dropdown.Option("mp4"), ft.dropdown.Option("mkv")],
            value="mp4",
            width=140,
        )
        self.output_dir_field = ft.Text(
            f"Destination: {getattr(self, 'output_folder', downloads_dir())}",
            selectable=True,
            expand=True,
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.cookies_file_field = ft.TextField(
            label="Cookies file (optional)",
            hint_text="Netscape-format .txt",
            width=240,
            height=56,
            read_only=True,
        )
        self.browser_drop = ft.Dropdown(
            label="Browser session (optional)",
            options=[
                ft.dropdown.Option("", "None"),
                ft.dropdown.Option("chrome", "Chrome"),
                ft.dropdown.Option("edge", "Microsoft Edge"),
                ft.dropdown.Option("firefox", "Firefox"),
                ft.dropdown.Option("brave", "Brave"),
                ft.dropdown.Option("opera", "Opera"),
                ft.dropdown.Option("chromium", "Chromium"),
                ft.dropdown.Option("vivaldi", "Vivaldi"),
                ft.dropdown.Option("safari", "Safari"),
            ],
            value="",
            width=240,
            on_select=self._on_browser_change,
        )
        self.skip_existing_checkbox = ft.Checkbox(
            label="Skip videos already downloaded",
            value=True,
        )
        self.video_progress = ft.ProgressBar(visible=False)
        self.video_status = ft.Text(
            "Ready to download",
            size=14,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.video_debug_log = ft.TextField(
            label="yt-dlp diagnostics",
            multiline=True,
            read_only=True,
            min_lines=3,
            max_lines=6,
            visible=False,
        )
        self.video_debug_toggle = ft.TextButton(
            "Show diagnostics",
            icon=ft.Icons.TERMINAL,
            on_click=self.toggle_video_debug,
        )

        self.queue_input = ft.TextField(
            label="Batch URLs",
            hint_text="Paste one video URL per line",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )
        self.queue_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.queue_summary = ft.Text(
            "0 pending",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.queue_panel = ft.Container(
            content=self.queue_list,
            height=250,
            padding=8,
            bgcolor=ft.Colors.TRANSPARENT,
            border_radius=8,
            visible=False,
        )

        single_button = ft.FilledButton(
            "Download video",
            icon=ft.Icons.DOWNLOAD,
            on_click=lambda e: asyncio.create_task(self.run_video_download(False)),
        )
        playlist_button = ft.FilledTonalButton(
            "Download playlist",
            icon=ft.Icons.PLAYLIST_PLAY,
            on_click=lambda e: asyncio.create_task(self.run_video_download(True)),
        )
        self.queue_add_button = ft.OutlinedButton(
            "Add to queue",
            icon=ft.Icons.ADD,
            on_click=self.add_queue_urls,
        )
        self.queue_start_button = ft.FilledButton(
            "Start queue",
            icon=ft.Icons.PLAY_ARROW,
            on_click=lambda e: asyncio.create_task(self.run_download_queue()),
        )
        self.queue_retry_button = ft.TextButton(
            "Retry failed",
            icon=ft.Icons.REPLAY,
            on_click=self.retry_failed_queue_items,
        )
        self.queue_clear_button = ft.TextButton(
            "Clear finished",
            icon=ft.Icons.CLEANING_SERVICES,
            on_click=self.clear_finished_queue_items,
        )
        self.video_download_buttons = [
            single_button,
            playlist_button,
            self.queue_add_button,
            self.queue_start_button,
        ]

        self.download_settings_panel = ft.Column(
            [
                ft.Column(
                    [
                        ft.Text(
                            "Download settings",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Choose a URL, format, quality and destination.",
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=2,
                ),
                self.video_url_field,
                ft.Row(
                    [self.download_type_drop, self.quality_drop, self.format_drop],
                    wrap=True,
                    spacing=12,
                ),
                ft.Row(
                    [
                        self.output_dir_field,
                        ft.OutlinedButton(
                            "Browse",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=self.choose_output_directory,
                        ),
                    ],
                    spacing=12,
                ),
                self.skip_existing_checkbox,
                ft.ExpansionTile(
                    title="Advanced: Authentication",
                    subtitle="Optional cookies for private or restricted videos",
                    leading=ft.Icons.COOKIE_OUTLINED,
                    controls=[
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        self.cookies_file_field,
                                        ft.OutlinedButton(
                                            "Select cookies",
                                            icon=ft.Icons.FOLDER_OPEN,
                                            on_click=self.choose_cookies_file,
                                        ),
                                    ],
                                    wrap=True,
                                    spacing=10,
                                ),
                                self.browser_drop,
                                ft.Text(
                                    "Choose either a cookies file or a browser session, not both. "
                                    "Firefox is recommended.",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    italic=True,
                                ),
                            ],
                            spacing=10,
                        )
                    ],
                ),
                ft.Row([single_button, playlist_button], wrap=True, spacing=10),
                self.video_progress,
                self.video_status,
                self.video_debug_toggle,
                self.video_debug_log,
            ],
            spacing=12,
        )
        download_queue = self._surface(
            ft.Column(
                [
                    self._section_heading(
                        "Download queue",
                        "Process multiple links sequentially.",
                        ft.Icons.PLAYLIST_PLAY,
                    ),
                    self.queue_input,
                    ft.Row(
                        [self.queue_add_button, self.queue_start_button],
                        wrap=True,
                        spacing=10,
                    ),
                    ft.Divider(),
                    ft.Row(
                        [
                            ft.Text("Queue", weight=ft.FontWeight.BOLD),
                            self.queue_summary,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    self.queue_panel,
                    ft.Row(
                        [self.queue_retry_button, self.queue_clear_button],
                        alignment=ft.MainAxisAlignment.END,
                        wrap=True,
                    ),
                ],
                spacing=14,
            ),
            padding=24,
        )

        self._render_page(
            ft.Column(
                [
                    self._section_heading(
                        "Video Lab",
                        "Download media from YouTube, Vimeo and other supported sites.",
                        ft.Icons.VIDEO_LIBRARY,
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                content=self.download_settings_panel,
                                expand=7,
                                bgcolor=ft.Colors.TRANSPARENT,
                            ),
                            ft.Container(
                                content=download_queue,
                                expand=5,
                            ),
                        ],
                        spacing=24,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                spacing=24,
            )
        )
        self._render_download_queue()
        self._set_download_actions_disabled(self.download_running)

    def _on_download_type_change(self, e):
        if self.download_type_drop.value == "mp3":
            self.quality_drop.options = [
                ft.dropdown.Option("320"),
                ft.dropdown.Option("192"),
                ft.dropdown.Option("128"),
            ]
            self.quality_drop.value = "192"
            self.format_drop.disabled = True
        else:
            self.quality_drop.options = [
                ft.dropdown.Option("best", "Best"),
                ft.dropdown.Option("1080"),
                ft.dropdown.Option("720"),
                ft.dropdown.Option("480"),
                ft.dropdown.Option("360"),
                ft.dropdown.Option("worst", "Worst"),
            ]
            self.quality_drop.value = "best"
            self.format_drop.disabled = False
        self.page.update()

    def _on_browser_change(self, e):
        if self.browser_drop.value:
            self.cookies_file_field.value = ""
        self.page.update()

    def toggle_video_debug(self, e=None):
        self.video_debug_log.visible = not self.video_debug_log.visible
        self.video_debug_toggle.text = (
            self._t("Hide diagnostics")
            if self.video_debug_log.visible
            else self._t("Show diagnostics")
        )
        self.page.update()

    async def choose_output_directory(self, e=None):
        selected = await self.file_picker.get_directory_path(
            dialog_title=self._t("Select the download folder"),
            initial_directory=self.output_folder,
        )
        if selected:
            self.output_folder = selected
            self.output_dir_field.value = f"Destination: {selected}"
            self.page.update()

    async def choose_cookies_file(self, e=None):
        files = await self.file_picker.pick_files(
            dialog_title=self._t("Select a cookies file"),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["txt"],
            allow_multiple=False,
        )
        if files and files[0].path:
            self.cookies_file_field.value = files[0].path
            self.browser_drop.value = ""
            self.page.update()

    def _get_download_options(self) -> dict[str, Any]:
        cookies_file = self.cookies_file_field.value.strip() or None
        browser = self.browser_drop.value or None
        if cookies_file and browser:
            raise ValueError("Choose a cookies file or a browser session, not both.")
        if cookies_file:
            self.video_lab._assert_usable_cookies(cookies_file)
        return {
            "quality": self.quality_drop.value or "best",
            "output_format": self.format_drop.value or "mp4",
            "download_type": self.download_type_drop.value or "video",
            "output_dir": self.output_folder or downloads_dir(),
            "skip_existing": self.skip_existing_checkbox.value,
            "cookies_file": cookies_file,
            "browser": browser,
        }

    def add_queue_urls(self, e=None):
        if self.download_running:
            return
        urls = [
            line.strip()
            for line in (self.queue_input.value or "").splitlines()
            if line.strip()
        ]
        if not urls:
            self._show_message("Add at least one URL to the queue.", ft.Colors.AMBER_200)
            return
        invalid_url = next(
            (url for url in urls if not url.startswith(("http://", "https://"))),
            None,
        )
        if invalid_url:
            self._show_message(
                f"Invalid URL: {invalid_url}. Links must start with http:// or https://.",
                ft.Colors.RED_200,
            )
            return
        for url in urls:
            self.download_queue.append(
                {
                    "id": self._next_queue_id,
                    "url": url,
                    "status": "Waiting",
                    "progress": 0,
                    "message": "",
                }
            )
            self._next_queue_id += 1
        self.queue_input.value = ""
        self._render_download_queue()

    def _render_download_queue(self):
        if not hasattr(self, "queue_list"):
            return
        self.queue_list.controls.clear()
        self.queue_panel.visible = bool(self.download_queue)

        colors = {
            "Waiting": ft.Colors.BLUE_400,
            "Downloading": ft.Colors.AMBER_600,
            "Completed": ft.Colors.TEAL_600,
            "Failed": ft.Colors.RED_600,
            "Stopped": ft.Colors.BLUE_GREY_500,
        }
        for item in self.download_queue:
            status = item["status"]
            color = colors.get(status, ft.Colors.GREY_600)
            content = [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.LINK,
                            size=16,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            item["url"],
                            size=13,
                            weight=ft.FontWeight.W_500,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Text(
                                status,
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            bgcolor=color,
                            padding=ft.Padding(8, 4, 8, 4),
                            border_radius=12,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            ]
            if status == "Downloading":
                content.extend(
                    [
                        ft.ProgressBar(
                            value=item.get("progress", 0),
                            color=color,
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                        ),
                        ft.Text(
                            item.get("message", "Downloading..."),
                            size=11,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ]
                )
            if status == "Failed":
                content.append(
                    ft.Text(item.get("error", ""), size=11, color=ft.Colors.RED_600)
                )
            if status == "Waiting":
                content[0].controls.append(
                    ft.IconButton(
                        ft.Icons.CLOSE,
                        icon_size=16,
                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                        tooltip="Remove from queue",
                        on_click=lambda e, queue_id=item["id"]: self.remove_queue_item(queue_id),
                    )
                )
            self.queue_list.controls.append(
                ft.Container(
                    content=ft.Column(content, spacing=6),
                    padding=12,
                    bgcolor=ft.Colors.TRANSPARENT,
                    border_radius=8,
                    margin=ft.Margin(0, 0, 0, 4),
                )
            )

        waiting = sum(item["status"] == "Waiting" for item in self.download_queue)
        completed = sum(item["status"] == "Completed" for item in self.download_queue)
        failed = sum(item["status"] == "Failed" for item in self.download_queue)
        stopped = sum(item["status"] == "Stopped" for item in self.download_queue)
        summary = (
            f"{waiting} {self._t('pending')} · "
            f"{completed} {self._t('completed items')} · "
            f"{failed} {self._t('failed items')}"
        )
        self.queue_summary.value = (
            f"{summary} · {stopped} {self._t('stopped items')}" if stopped else summary
        )
        self.queue_start_button.disabled = self.download_running or waiting == 0
        self.queue_retry_button.disabled = self.download_running or failed == 0
        self.queue_clear_button.disabled = (
            self.download_running or (completed == 0 and failed == 0 and stopped == 0)
        )
        self._translate_control(self.queue_list)
        self.page.update()

    def remove_queue_item(self, queue_id: int):
        if self.download_running:
            return
        self.download_queue = [
            item
            for item in self.download_queue
            if item["id"] != queue_id or item["status"] != "Waiting"
        ]
        self._render_download_queue()

    def clear_finished_queue_items(self, e=None):
        if self.download_running:
            return
        self.download_queue = [
            item
            for item in self.download_queue
            if item["status"] not in {"Completed", "Failed", "Stopped"}
        ]
        self._render_download_queue()

    def retry_failed_queue_items(self, e=None):
        if self.download_running:
            return
        for item in self.download_queue:
            if item["status"] == "Failed":
                item["status"] = "Waiting"
                item.pop("error", None)
        self._render_download_queue()

    def _set_download_actions_disabled(self, disabled: bool):
        for button in getattr(self, "video_download_buttons", []):
            button.disabled = disabled
        if hasattr(self, "queue_input"):
            self.queue_input.disabled = disabled
        if hasattr(self, "queue_retry_button"):
            self.queue_retry_button.disabled = disabled or not any(
                item["status"] == "Failed" for item in self.download_queue
            )
        if hasattr(self, "queue_clear_button"):
            self.queue_clear_button.disabled = disabled or not any(
                item["status"] in {"Completed", "Failed", "Stopped"}
                for item in self.download_queue
            )

    async def run_download_queue(self, e=None):
        if self.download_running:
            return
        pending = [item for item in self.download_queue if item["status"] == "Waiting"]
        if not pending:
            self._show_message("Add at least one URL before starting the queue.", ft.Colors.AMBER_200)
            return
        try:
            options = self._get_download_options()
        except ValueError as exc:
            self._show_message(str(exc), ft.Colors.RED_200)
            return

        self.download_running = True
        self.download_cancel_event.clear()
        self._set_stop_download_visible(True)
        self.video_progress.visible = True
        self._set_download_actions_disabled(True)
        completed = 0
        failed = 0
        stopped = False
        try:
            for item in pending:
                if self.download_cancel_event.is_set():
                    stopped = True
                    break
                item["status"] = "Downloading"
                self._active_queue_item_id = item["id"]
                self._render_download_queue()
                try:
                    await self._download_one(
                        item["url"],
                        is_playlist=False,
                        options=options,
                    )
                except DownloadCancelled:
                    item["status"] = "Stopped"
                    stopped = True
                    self._render_download_queue()
                    break
                except Exception as exc:
                    item["status"] = "Failed"
                    item["error"] = str(exc)
                    failed += 1
                else:
                    item["status"] = "Completed"
                    item["progress"] = 1
                    completed += 1
                self._render_download_queue()
        finally:
            self._active_queue_item_id = None
            self.download_running = False
            self._set_stop_download_visible(False)
            self.video_progress.visible = False
            self._set_download_actions_disabled(False)
            self._render_download_queue()

        if stopped:
            self._show_message(
                f"{self._t('Queue stopped: ')}{completed} "
                f"{self._t('completed items')}, {failed} {self._t('failed items')}.",
                ft.Colors.AMBER_200,
            )
        else:
            self._show_message(
                f"{self._t('Queue finished: ')}{completed} "
                f"{self._t('completed items')}, {failed} {self._t('failed items')}.",
                ft.Colors.TEAL_100 if failed == 0 else ft.Colors.AMBER_200,
            )

    async def run_video_download(self, is_playlist: bool):
        if self.download_running:
            return
        url = (self.video_url_field.value or "").strip()
        if not url.startswith(("http://", "https://")):
            self._show_message(
                "Enter a valid http:// or https:// URL.",
                ft.Colors.RED_200,
            )
            return
        try:
            options = self._get_download_options()
        except ValueError as exc:
            self._show_message(str(exc), ft.Colors.RED_200)
            return

        self.download_running = True
        self.download_cancel_event.clear()
        self._set_stop_download_visible(True)
        self.video_progress.visible = True
        self.video_progress.value = None
        self._set_download_actions_disabled(True)
        try:
            path = await self._download_one(url, is_playlist, options)
        except DownloadCancelled:
            self.video_status.value = self._t("Download stopped.")
            self._show_message("Download stopped.", ft.Colors.AMBER_200)
        except Exception as exc:
            self.video_status.value = self._t(f"Download failed: {exc}")
            self._show_message(f"Download failed: {exc}", ft.Colors.RED_200)
        else:
            self.video_progress.value = 1
            self.video_status.value = self._t(f"Download complete: {path}")
            self._show_message(f"Download complete: {path}")
        finally:
            self.download_running = False
            self._set_stop_download_visible(False)
            self.video_progress.visible = False
            self._set_download_actions_disabled(False)
            self.page.update()

    async def _download_one(
        self,
        url: str,
        is_playlist: bool,
        options: dict[str, Any],
    ) -> str:
        normalized_url, platform = self.video_lab.normalize_url(url)
        self.video_status.value = self._t(f"Connecting to {platform}...")
        self.page.update()
        progress_events: Queue[dict[str, Any]] = Queue()

        def on_progress(event: dict[str, Any]):
            if self.download_cancel_event.is_set():
                raise DownloadCancelled("Download stopped by user.")
            progress_events.put(event)

        download_task = asyncio.create_task(
            asyncio.to_thread(
                self.video_lab.download_video,
                normalized_url,
                options["quality"],
                options["output_format"],
                download_type=options["download_type"],
                is_playlist=is_playlist,
                output_dir=options["output_dir"],
                skip_existing=options.get("skip_existing", True),
                cookies_file=options.get("cookies_file"),
                browser=options.get("browser"),
                progress_hook=on_progress,
            )
        )
        while not download_task.done():
            self._update_video_progress(progress_events)
            await asyncio.sleep(0.3)
        self._update_video_progress(progress_events)
        return await download_task

    def _update_video_progress(self, progress_events: Queue[dict[str, Any]]):
        latest = None
        debug_messages = []
        while True:
            try:
                event = progress_events.get_nowait()
            except Empty:
                break
            if event.get("status") == "debug":
                debug_messages.append(event.get("message", ""))
            elif event.get("status") in {"downloading", "finished"}:
                latest = event

            queue_id = getattr(self, "_active_queue_item_id", None)
            if queue_id is not None and event.get("status") == "downloading":
                for item in self.download_queue:
                    if item["id"] == queue_id:
                        total = event.get("total_bytes") or event.get("total_bytes_estimate") or 0
                        item["progress"] = (
                            min(event.get("downloaded_bytes", 0) / total, 1)
                            if total
                            else 0
                        )
                        item["message"] = Path(event.get("filename", "")).name

        if debug_messages:
            existing = self.video_debug_log.value.splitlines() if self.video_debug_log.value else []
            self.video_debug_log.value = "\n".join((existing + debug_messages)[-200:])
        if latest:
            if latest.get("status") == "downloading":
                total = latest.get("total_bytes") or latest.get("total_bytes_estimate") or 0
                downloaded = latest.get("downloaded_bytes", 0)
                self.video_progress.value = min(downloaded / total, 1) if total else None
                filename = Path(latest.get("filename", "")).name
                self.video_status.value = self._t(f"Downloading: {filename}")
            elif latest.get("status") == "finished":
                self.video_progress.value = 1
                self.video_status.value = self._t("Finalizing file...")
        self._render_download_queue()
