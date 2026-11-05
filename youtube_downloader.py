import argparse
import os
import re
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse, parse_qs

import markdown_utils
import lamovie
import torrent_downloader


_current_process = None


def _run_cmd(cmd, output_dir=None):
    global _current_process
    _current_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    output, _ = _current_process.communicate()
    returncode = _current_process.returncode
    _current_process = None
    if returncode != 0:
        if output_dir and os.path.exists(output_dir):
            has_files = any(
                f.endswith((".mp4", ".webm", ".mkv", ".m4a", ".mp3"))
                for f in os.listdir(output_dir)
                if os.path.isfile(os.path.join(output_dir, f))
            )
            if has_files:
                print(f"Advertencia: yt-dlp terminó con código {returncode}, pero hay archivos descargados.")
                return
        raise subprocess.CalledProcessError(returncode, cmd, output=output)


def check_yt_dlp():
    try:
        subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            check=True
        )


def _build_video_format(quality):
    if quality == "best":
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    return f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"


def download_video(url, output_dir="downloads/video", quality="best", archive_file=None, cookies_file=None):
    os.makedirs(output_dir, exist_ok=True)

    format_str = _build_video_format(quality)

    cmd = [
        "yt-dlp",
        "-f", format_str,
        "--merge-output-format", "mp4",
        "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
        "--no-playlist",
        "--ignore-errors",
    ]

    if archive_file:
        cmd.extend(["--download-archive", archive_file])
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
    cmd.append(url)

    _run_cmd(cmd, output_dir)


def download_mp3(url, output_dir="downloads/mp3", quality="192", archive_file=None, cookies_file=None):
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", quality,
        "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
        "--no-playlist",
        "--ignore-errors",
    ]

    if archive_file:
        cmd.extend(["--download-archive", archive_file])
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
    cmd.append(url)

    _run_cmd(cmd, output_dir)


def extract_playlist_id(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return params.get("list", [None])[0]


def download_playlist_video(url, output_dir="downloads/video", quality="best", archive_file=None, cookies_file=None):
    os.makedirs(output_dir, exist_ok=True)

    format_str = _build_video_format(quality)

    cmd = [
        "yt-dlp",
        "-f", format_str,
        "--merge-output-format", "mp4",
        "-o", os.path.join(output_dir, "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"),
        "--yes-playlist",
        "--ignore-errors",
    ]

    if archive_file:
        cmd.extend(["--download-archive", archive_file])
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])

    cmd.append(url)

    _run_cmd(cmd, output_dir)


def download_playlist_mp3(url, output_dir="downloads/mp3", quality="192", archive_file=None, cookies_file=None):
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", quality,
        "-o", os.path.join(output_dir, "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"),
        "--yes-playlist",
        "--ignore-errors",
    ]

    if archive_file:
        cmd.extend(["--download-archive", archive_file])
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])

    cmd.append(url)

    _run_cmd(cmd, output_dir)


class DownloaderUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Downloader")
        self.root.geometry("700x550")
        self.root.resizable(False, False)

        self.download_queue = queue.Queue()
        self.is_downloading = False
        self.current_process = None
        self.cancel_event = threading.Event()

        self._create_widgets()

    def _create_widgets(self):
        style = ttk.Style()
        style.configure("TButton", padding=6, font=("Segoe UI", 10))
        style.configure("TLabel", font=("Segoe UI", 10))

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(main_frame, text="Video Downloader", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 20)
        )

        ttk.Label(main_frame, text="URL del video/playlist (YouTube, Vimeo, etc.):").grid(
            row=1, column=0, sticky=tk.W, pady=(0, 5)
        )
        self.url_entry = ttk.Entry(main_frame, width=60)
        self.url_entry.grid(row=2, column=0, columnspan=2, pady=(0, 15), sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Tipo de descarga:").grid(
            row=3, column=0, sticky=tk.W, pady=(0, 5)
        )
        self.download_type = tk.StringVar(value="video")
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))
        ttk.Radiobutton(type_frame, text="Video (MP4)", variable=self.download_type,
                        value="video").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(type_frame, text="Audio (MP3)", variable=self.download_type,
                        value="mp3").pack(side=tk.LEFT)

        ttk.Label(main_frame, text="Calidad:").grid(
            row=5, column=0, sticky=tk.W, pady=(0, 5)
        )
        self.quality = tk.StringVar(value="best")
        quality_frame = ttk.Frame(main_frame)
        quality_frame.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))

        self.video_quality = ttk.Combobox(quality_frame, textvariable=self.quality,
                                          values=["best", "1080", "720", "480", "360"],
                                          state="readonly", width=10)
        self.video_quality.pack(side=tk.LEFT)
        self.video_quality.set("best")

        ttk.Label(main_frame, text="Carpeta de destino:").grid(
            row=7, column=0, sticky=tk.W, pady=(0, 5)
        )
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        self.output_var = tk.StringVar(value="downloads")
        ttk.Entry(output_frame, textvariable=self.output_var, width=50).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(output_frame, text="Buscar", command=self._browse_folder).pack(side=tk.LEFT)

        self.skip_existing = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Omitir videos ya descargados",
                        variable=self.skip_existing).grid(
            row=9, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        ttk.Label(main_frame, text="Archivo de cookies (opcional):").grid(
            row=10, column=0, sticky=tk.W, pady=(0, 5)
        )
        cookies_frame = ttk.Frame(main_frame)
        cookies_frame.grid(row=11, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        self.cookies_var = tk.StringVar()
        ttk.Entry(cookies_frame, textvariable=self.cookies_var, width=50).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(cookies_frame, text="Buscar", command=self._browse_cookies).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(cookies_frame, text="Exportar del navegador", command=self._export_cookies_from_browser).pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(main_frame, mode="indeterminate", length=400)
        self.progress.grid(row=12, column=0, columnspan=2, pady=(10, 10))

        self.status_label = ttk.Label(main_frame, text="Listo", foreground="gray")
        self.status_label.grid(row=13, column=0, columnspan=2, pady=(0, 10))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=14, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frame, text="Descargar", command=self._start_download).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Descargar Playlist", command=self._start_playlist_download).pack(side=tk.LEFT, padx=(0, 10))
        self.cancel_btn = ttk.Button(btn_frame, text="Cancelar", command=self._cancel_download, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Markdown", command=self._start_markdown).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Limpiar", command=self._clear).pack(side=tk.LEFT)

    def _browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)

    def _browse_cookies(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            self.cookies_var.set(file)

    def _export_cookies_from_browser(self):
        try:
            output_dir = self.output_var.get()
            os.makedirs(output_dir, exist_ok=True)
            cookies_path = os.path.join(output_dir, "cookies.txt")

            browsers = ["firefox", "chrome", "edge", "brave", "opera", "chromium", "vivaldi", "safari"]
            available = []
            for browser in browsers:
                try:
                    result = subprocess.run(
                        ["yt-dlp", "--cookies-from-browser", browser, "--simulate", "--no-warnings", "https://vimeo.com"],
                        capture_output=True, text=True, timeout=10
                    )
                    available.append(browser)
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

            if not available:
                messagebox.showerror("Error", "No se encontraron navegadores compatibles con cookies.")
                return

            if len(available) == 1:
                selected = available[0]
            else:
                selected = self._ask_browser(available)
                if not selected:
                    return

            self.cookies_var.set(cookies_path)
            self.status_label.config(text=f"Exportando cookies de {selected}...", foreground="blue")
            self.root.update()

            bat_path = os.path.join(output_dir, "export_cookies.bat")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(f'@echo off\n')
                f.write(f'echo Exportando cookies de {selected}...\n')
                f.write(f'echo.\n')
                f.write(f'echo IMPORTANTE: Si el navegador esta abierto, cerrarlo antes de continuar.\n')
                f.write(f'echo.\n')
                f.write(f'yt-dlp --cookies-from-browser {selected} --cookies "{cookies_path}" --simulate "https://vimeo.com"\n')
                f.write(f'echo.\n')
                f.write(f'if %ERRORLEVEL% EQU 0 (\n')
                f.write(f'    echo Cookies exportados exitosamente a: {cookies_path}\n')
                f.write(f') else (\n')
                f.write(f'    echo Error al exportar cookies.\n')
                f.write(f'    echo.\n')
                f.write(f'    echo Si ves "Failed to decrypt with DPAPI", usa este metodo alternativo:\n')
                f.write(f'    echo 1. Instala la extension "Get cookies.txt LOCALLY" en tu navegador\n')
                f.write(f'    echo 2. Exporta las cookies de vimeo.com\n')
                f.write(f'    echo 3. Guarda el archivo como cookies.txt en: {output_dir}\n')
                f.write(f')\n')
                f.write(f'pause\n')

            subprocess.Popen(["cmd", "/c", bat_path])

            messagebox.showinfo("Info", f"Se ejecutó el script para exportar cookies de {selected}.\n"
                              f"IMPORTANTE: Cierra el navegador si está abierto.\n"
                              f"Cuando termine, las cookies estarán en:\n{cookies_path}\n\n"
                              f"Si ves 'Failed to decrypt with DPAPI', usa la extensión "
                              f"'Get cookies.txt LOCALLY' para exportar cookies manualmente.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar cookies: {str(e)}")

    def _ask_browser(self, browsers):
        dialog = tk.Toplevel(self.root)
        dialog.title("Seleccionar navegador")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()

        selected = tk.StringVar(value=browsers[0])

        ttk.Label(dialog, text="Selecciona tu navegador:").pack(pady=10)
        for browser in browsers:
            ttk.Radiobutton(dialog, text=browser.capitalize(), variable=selected, value=browser).pack(anchor=tk.W, padx=20)

        result = [None]

        def on_ok():
            result[0] = selected.get()
            dialog.destroy()

        ttk.Button(dialog, text="OK", command=on_ok).pack(pady=10)

        self.root.wait_window(dialog)
        return result[0]

    def _clear(self):
        self.url_entry.delete(0, tk.END)
        self.status_label.config(text="Listo", foreground="gray")

    def _cancel_download(self):
        global _current_process
        if _current_process and self.is_downloading:
            self.cancel_event.set()
            _current_process.terminate()
            self.is_downloading = False
            self.progress.stop()
            self.cancel_btn.config(state=tk.DISABLED)
            self.status_label.config(text="Descarga cancelada", foreground="orange")

    def _get_downloaded_files(self):
        output_base = self.output_var.get()
        downloaded = set()
        for root_dir, _, files in os.walk(output_base):
            for f in files:
                if f.endswith((".mp4", ".mp3", ".m4a", ".webm")):
                    downloaded.add(f)
        return downloaded

    def _check_existing_content(self):
        output_base = self.output_var.get()
        if not os.path.exists(output_base):
            return 0, 0

        files = []
        for root_dir, _, filenames in os.walk(output_base):
            for f in filenames:
                if f.endswith((".mp4", ".mp3", ".m4a", ".webm")):
                    files.append(os.path.join(root_dir, f))

        total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
        return len(files), total_size

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Advertencia", "Ingresa una URL válida")
            return

        if not url.startswith(("http://", "https://")):
            messagebox.showwarning("Advertencia", "La URL debe comenzar con http:// o https://")
            return

        if self.is_downloading:
            messagebox.showinfo("Info", "Ya hay una descarga en progreso")
            return

        existing_count, existing_size = self._check_existing_content()
        if existing_count > 0:
            size_mb = existing_size / (1024 * 1024)
            self.status_label.config(
                text=f"{existing_count} archivos ya descargados ({size_mb:.1f} MB). Listo para nuevos.",
                foreground="green"
            )

        self.is_downloading = True
        self.cancel_event.clear()
        self.progress.start()
        self.cancel_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Descargando...", foreground="blue")

        thread = threading.Thread(target=self._download_thread, args=(url, False))
        thread.daemon = True
        thread.start()

    def _start_playlist_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Advertencia", "Ingresa una URL de playlist válida")
            return

        if not url.startswith(("http://", "https://")):
            messagebox.showwarning("Advertencia", "La URL debe comenzar con http:// o https://")
            return

        if self.is_downloading:
            messagebox.showinfo("Info", "Ya hay una descarga en progreso")
            return

        self.is_downloading = True
        self.progress.start()
        self.status_label.config(text="Descargando playlist...", foreground="blue")

        thread = threading.Thread(target=self._playlist_download_thread, args=(url, True))
        thread.daemon = True
        thread.start()

    def _start_markdown(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Advertencia", "Ingresa una URL válida")
            return

        if not url.startswith(("http://", "https://")):
            messagebox.showwarning("Advertencia", "La URL debe comenzar con http:// o https://")
            return

        output_base = self.output_var.get()
        path = os.path.join(output_base, "markdown", markdown_utils.slug_from_url(url) + ".md")

        thread = threading.Thread(target=self._markdown_thread, args=(url, path))
        thread.daemon = True
        thread.start()

    def _markdown_thread(self, url, path):
        try:
            self.root.after(0, lambda: self.status_label.config(text="Generando Markdown...", foreground="blue"))
            markdown_utils.generate_markdown(url, path)
            self.root.after(0, lambda: self._markdown_complete(path))
        except Exception as e:
            self.root.after(0, lambda: self._markdown_failed(str(e)))

    def _markdown_complete(self, path):
        self.status_label.config(text=f"Markdown guardado: {path}", foreground="green")
        messagebox.showinfo("Éxito", f"Markdown guardado en:\n{path}")

    def _markdown_failed(self, error):
        self.status_label.config(text=f"Error: {error}", foreground="red")
        messagebox.showerror("Error", error)

    def _lamovie_resolved(self, resolved, path):
        self.progress.stop()
        self.is_downloading = False
        self.cancel_btn.config(state=tk.DISABLED)
        lines = [f"Título: {resolved['title']}", ""]
        if resolved["embeds"]:
            lines.append("Enlaces de reproducción:")
            for embed in resolved["embeds"]:
                lines.append(
                    f"  [{embed.get('server')} | {embed.get('lang')} | "
                    f"{embed.get('quality')}]\n  {embed['url']}"
                )
            lines.append("")
        if resolved["downloads"]:
            lines.append("Descargas:")
            for download in resolved["downloads"]:
                lines.append(
                    f"  [{download.get('server')} | {download.get('lang')} | "
                    f"{download.get('quality')}]\n  {download['url']}"
                )
            lines.append("")
        if path:
            lines.append(f"Markdown guardado en:\n{path}")

        magnet = next(
            (d["url"] for d in resolved["downloads"] if d.get("server") == "Torrent"),
            None,
        )

        if magnet and torrent_downloader.is_available():
            lines.append("¿Descargar el torrent directamente?")
            message = "\n".join(lines)
            if messagebox.askyesno("Enlaces resueltos", message):
                self._start_torrent_download(magnet, resolved["title"])
                return

        lines.append(
            "lamovie.org no es soportado por yt-dlp. Usa los enlaces "
            "(torrent con qBittorrent, o JDownloader 2)."
        )
        message = "\n".join(lines)
        self.status_label.config(text="Enlaces de lamovie resueltos", foreground="green")
        messagebox.showinfo("Enlaces resueltos", message)

    def _start_torrent_download(self, magnet, title):
        self.is_downloading = True
        self.progress.start()
        self.cancel_btn.config(state=tk.NORMAL)
        self.status_label.config(text=f"Descargando: {title}", foreground="blue")

        thread = threading.Thread(target=self._torrent_thread, args=(magnet, title))
        thread.daemon = True
        thread.start()

    def _torrent_thread(self, magnet, title):
        try:
            def _cb(event):
                if isinstance(event, dict):
                    if event.get("type") == "log":
                        return
                    stage = event.get("stage")
                    if stage == "metadata":
                        self.root.after(
                            0, lambda: self.status_label.config(text="Obteniendo metadata...")
                        )
                        return
                    progress = event.get("progress") or 0
                    rate = event.get("download_rate", 0)
                    peers = event.get("peers", 0)
                    pct = f"{progress*100:.1f}%"
                    self.root.after(
                        0,
                        lambda: self.status_label.config(
                            text=f"{pct} | {rate/1024:.0f} KB/s | peers {peers}"
                        ),
                    )

            result = torrent_downloader.download_torrent(
                magnet, "downloads/torrent", progress_callback=_cb
            )
            self.root.after(0, lambda: self._torrent_complete(result))
        except Exception as e:
            self.root.after(0, lambda: self._torrent_failed(str(e)))

    def _torrent_complete(self, result):
        self.progress.stop()
        self.is_downloading = False
        self.cancel_btn.config(state=tk.DISABLED)
        self.status_label.config(text=f"Completado: {result['name']}", foreground="green")
        messagebox.showinfo(
            "Éxito",
            f"{result['name']}\n{result['size']/(1024**3):.2f} GB\n\n"
            f"Guardado en:\n{result['path']}",
        )

    def _torrent_failed(self, error):
        self.progress.stop()
        self.is_downloading = False
        self.cancel_btn.config(state=tk.DISABLED)
        self.status_label.config(text=f"Error: {error}", foreground="red")
        messagebox.showerror("Error", error)

    def _get_archive_file(self):
        if self.skip_existing.get():
            output_base = self.output_var.get()
            return os.path.join(output_base, "downloaded.txt")
        return None

    def _get_cookies_file(self):
        return self.cookies_var.get().strip() or None

    def _playlist_download_thread(self, url, force_playlist=True):
        try:
            check_yt_dlp()

            download_type = self.download_type.get()
            quality = self.quality.get()
            output_base = self.output_var.get()
            archive_file = self._get_archive_file()
            cookies_file = self._get_cookies_file()

            if download_type == "mp3":
                download_playlist_mp3(url, os.path.join(output_base, "mp3"), quality, archive_file, cookies_file)
            else:
                download_playlist_video(url, os.path.join(output_base, "video"), quality, archive_file, cookies_file)

            if not self.cancel_event.is_set():
                self.root.after(0, self._download_complete, True, "Playlist descargada!")
        except Exception as e:
            if not self.cancel_event.is_set():
                self.root.after(0, self._download_complete, False, str(e))

    def _download_thread(self, url, force_playlist=False):
        try:
            if "lamovie.org" in url:
                try:
                    resolved = lamovie.resolve_lamovie(url)
                except ValueError as e:
                    self.root.after(0, lambda: self._download_complete(False, str(e)))
                    return
                output_base = self.output_var.get()
                path = os.path.join(
                    output_base, "markdown", markdown_utils.slug_from_url(url) + ".md"
                )
                try:
                    markdown_utils.generate_markdown(url, path)
                except Exception:
                    path = None
                self.root.after(0, lambda: self._lamovie_resolved(resolved, path))
                return

            check_yt_dlp()

            download_type = self.download_type.get()
            quality = self.quality.get()
            output_base = self.output_var.get()
            archive_file = self._get_archive_file()
            cookies_file = self._get_cookies_file()
            is_playlist = force_playlist

            if is_playlist:
                if download_type == "mp3":
                    download_playlist_mp3(url, os.path.join(output_base, "mp3"), quality, archive_file, cookies_file)
                else:
                    download_playlist_video(url, os.path.join(output_base, "video"), quality, archive_file, cookies_file)
            else:
                if download_type == "mp3":
                    download_mp3(url, os.path.join(output_base, "mp3"), quality, archive_file, cookies_file)
                else:
                    download_video(url, os.path.join(output_base, "video"), quality, archive_file, cookies_file)

            if not self.cancel_event.is_set():
                self.root.after(0, self._download_complete, True, "Descarga completada!")
        except Exception as e:
            if not self.cancel_event.is_set():
                self.root.after(0, self._download_complete, False, str(e))

    def _download_complete(self, success, message):
        self.progress.stop()
        self.is_downloading = False
        self.cancel_btn.config(state=tk.DISABLED)
        if success:
            self.status_label.config(text=message, foreground="green")
            messagebox.showinfo("Éxito", message)
        else:
            self.status_label.config(text=f"Error: {message}", foreground="red")
            messagebox.showerror("Error", message)


class TestDownloader(unittest.TestCase):
    def _get_module_name(self):
        return "__main__" if __name__ == "__main__" else "youtube_downloader"

    @patch("youtube_downloader.subprocess.run")
    def test_check_yt_dlp_already_installed(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        check_yt_dlp()
        mock_run.assert_called_once()

    @patch("youtube_downloader.subprocess.run")
    def test_check_yt_dlp_installs_when_missing(self, mock_run):
        mock_run.side_effect = [FileNotFoundError, MagicMock()]
        check_yt_dlp()
        self.assertEqual(mock_run.call_count, 2)

    def test_download_video(self):
        mod = self._get_module_name()
        with patch(f"{mod}._run_cmd") as mock_run, patch(f"{mod}.os.makedirs") as mock_makedirs:
            download_video("https://youtube.com/watch?v=test", "test_out", "best")
            mock_makedirs.assert_called_once_with("test_out", exist_ok=True)
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            self.assertIn("yt-dlp", cmd)
            self.assertIn("--merge-output-format", cmd)

    def test_download_mp3(self):
        mod = self._get_module_name()
        with patch(f"{mod}._run_cmd") as mock_run, patch(f"{mod}.os.makedirs") as mock_makedirs:
            download_mp3("https://youtube.com/watch?v=test", "test_out", "320")
            mock_makedirs.assert_called_once_with("test_out", exist_ok=True)
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            self.assertIn("-x", cmd)
            self.assertIn("--audio-format", cmd)
            self.assertIn("mp3", cmd)

    def test_download_playlist_video(self):
        mod = self._get_module_name()
        with patch(f"{mod}._run_cmd") as mock_run, patch(f"{mod}.os.makedirs") as mock_makedirs:
            download_playlist_video("https://youtube.com/playlist?list=test", "test_out")
            mock_makedirs.assert_called_once()
            cmd = mock_run.call_args[0][0]
            self.assertIn("%(playlist_title)s", cmd[cmd.index("-o") + 1])

    def test_download_playlist_mp3(self):
        mod = self._get_module_name()
        with patch(f"{mod}._run_cmd") as mock_run, patch(f"{mod}.os.makedirs") as mock_makedirs:
            download_playlist_mp3("https://youtube.com/playlist?list=test", "test_out")
            mock_makedirs.assert_called_once()
            cmd = mock_run.call_args[0][0]
            self.assertIn("-x", cmd)
            self.assertIn("%(playlist_title)s", cmd[cmd.index("-o") + 1])

    def test_extract_playlist_id_from_watch_url(self):
        url = "https://www.youtube.com/watch?v=AlbvHKqVhcI&list=PL_QELklswYG6QOTCIIBew_cH1CWhCoJmk"
        result = extract_playlist_id(url)
        self.assertEqual(result, "PL_QELklswYG6QOTCIIBew_cH1CWhCoJmk")

    def test_extract_playlist_id_from_playlist_url(self):
        url = "https://www.youtube.com/playlist?list=PL_QELklswYG6QOTCIIBew_cH1CWhCoJmk"
        result = extract_playlist_id(url)
        self.assertEqual(result, "PL_QELklswYG6QOTCIIBew_cH1CWhCoJmk")

    def test_extract_playlist_id_no_list_param(self):
        url = "https://www.youtube.com/watch?v=AlbvHKqVhcI"
        result = extract_playlist_id(url)
        self.assertIsNone(result)

    def test_download_playlist_video_with_quality(self):
        mod = self._get_module_name()
        with patch(f"{mod}._run_cmd") as mock_run, patch(f"{mod}.os.makedirs"):
            download_playlist_video("https://youtube.com/playlist?list=test", "test_out", "720")
            cmd = mock_run.call_args[0][0]
            self.assertIn("720", cmd[cmd.index("-f") + 1])
            self.assertIn("--yes-playlist", cmd)

    def test_download_playlist_mp3_with_quality(self):
        mod = self._get_module_name()
        with patch(f"{mod}._run_cmd") as mock_run, patch(f"{mod}.os.makedirs"):
            download_playlist_mp3("https://youtube.com/playlist?list=test", "test_out", "320")
            cmd = mock_run.call_args[0][0]
            self.assertIn("320", cmd[cmd.index("--audio-quality") + 1])
            self.assertIn("--yes-playlist", cmd)

    def test_download_video_with_archive(self):
        mod = self._get_module_name()
        with patch(f"{mod}._run_cmd") as mock_run, patch(f"{mod}.os.makedirs"):
            download_video("https://youtube.com/watch?v=test", "test_out", "best", "archive.txt")
            cmd = mock_run.call_args[0][0]
            self.assertIn("--download-archive", cmd)
            self.assertIn("archive.txt", cmd[cmd.index("--download-archive") + 1])

    def test_download_mp3_with_archive(self):
        mod = self._get_module_name()
        with patch(f"{mod}._run_cmd") as mock_run, patch(f"{mod}.os.makedirs"):
            download_mp3("https://youtube.com/watch?v=test", "test_out", "192", "archive.txt")
            cmd = mock_run.call_args[0][0]
            self.assertIn("--download-archive", cmd)
            self.assertIn("archive.txt", cmd[cmd.index("--download-archive") + 1])

    def test_download_playlist_video_with_archive(self):
        mod = self._get_module_name()
        with patch(f"{mod}._run_cmd") as mock_run, patch(f"{mod}.os.makedirs"):
            download_playlist_video("https://youtube.com/playlist?list=test", "test_out", "best", "archive.txt")
            cmd = mock_run.call_args[0][0]
            self.assertIn("--download-archive", cmd)
            self.assertIn("archive.txt", cmd[cmd.index("--download-archive") + 1])

    def test_download_playlist_mp3_with_archive(self):
        mod = self._get_module_name()
        with patch(f"{mod}._run_cmd") as mock_run, patch(f"{mod}.os.makedirs"):
            download_playlist_mp3("https://youtube.com/playlist?list=test", "test_out", "192", "archive.txt")
            cmd = mock_run.call_args[0][0]
            self.assertIn("--download-archive", cmd)
            self.assertIn("archive.txt", cmd[cmd.index("--download-archive") + 1])


def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestDownloader)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description="Descargador de videos - Video o MP3")
    parser.add_argument("url", nargs="?", help="URL del video o playlist (YouTube, Vimeo, etc.)")
    parser.add_argument("-t", "--type", choices=["video", "mp3"], default="video")
    parser.add_argument("-q", "--quality", default="best")
    parser.add_argument("-o", "--output", help="Directorio de salida")
    parser.add_argument("-p", "--playlist", action="store_true",
                        help="Forzar descarga como playlist")
    parser.add_argument("--no-skip", action="store_true",
                        help="No omitir videos ya descargados")
    parser.add_argument("--cookies", help="Archivo de cookies para sitios que requieren login")
    parser.add_argument("--markdown", action="store_true",
                        help="Generar un archivo Markdown desde la URL (en lugar de descargar)")
    parser.add_argument("--gui", action="store_true", help="Interfaz gráfica")
    parser.add_argument("--test", action="store_true", help="Ejecutar pruebas unitarias")

    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    if args.markdown:
        if not args.url:
            parser.error("--markdown requiere una URL")
        slug = markdown_utils.slug_from_url(args.url)
        output = args.output
        if not output:
            output = os.path.join("downloads", "markdown", slug + ".md")
        elif not output.lower().endswith(".md"):
            output = os.path.join(output, slug + ".md")
        markdown_utils.generate_markdown(args.url, output)
        print(f"Markdown guardado en: {output}")
        return

    if args.url and "lamovie.org" in args.url:
        try:
            resolved = lamovie.resolve_lamovie(args.url)
        except ValueError as e:
            print(f"\nError: {e}")
            sys.exit(1)

        print(f"\nTitulo: {resolved['title']}")
        if resolved["embeds"]:
            print("\nEnlaces de reproduccion:")
            for embed in resolved["embeds"]:
                print(
                    f"  - [{embed.get('server')} | {embed.get('lang')} | "
                    f"{embed.get('quality')}] {embed['url']}"
                )
        if resolved["downloads"]:
            print("\nDescargas:")
            for download in resolved["downloads"]:
                print(
                    f"  - [{download.get('server')} | {download.get('lang')} | "
                    f"{download.get('quality')}] {download['url']}"
                )

        output = os.path.join(
            "downloads", "markdown", markdown_utils.slug_from_url(args.url) + ".md"
        )
        markdown_utils.generate_markdown(args.url, output)
        print(f"\nMarkdown guardado en: {output}")

        magnet = next(
            (d["url"] for d in resolved["downloads"] if d.get("server") == "Torrent"),
            None,
        )
        if magnet and torrent_downloader.is_available():
            print(f"\nIniciando descarga del torrent: {resolved['title']}")
            print("Ctrl+C para detener.\n")

            def _cb(event):
                if isinstance(event, dict):
                    if event.get("type") == "log":
                        return
                    stage = event.get("stage")
                    if stage == "metadata":
                        print("Obteniendo metadata...")
                        return
                    progress = event.get("progress") or 0
                    rate = event.get("download_rate", 0)
                    peers = event.get("peers", 0)
                    seeds = event.get("seeds", 0)
                    print(
                        f"\r{progress*100:5.1f}% | {rate/1024:7.0f} KB/s | "
                        f"peers {peers} seeds {seeds}   ",
                        end="",
                        flush=True,
                    )

            try:
                result = torrent_downloader.download_torrent(
                    magnet, "downloads/torrent", progress_callback=_cb
                )
                print(f"\nCompletado: {result['name']}")
                print(f"Guardado en: {result['path']}")
            except KeyboardInterrupt:
                print("\nDescarga cancelada por el usuario.")
            except Exception as e:
                print(f"\nError en la descarga: {e}")
        elif magnet:
            print(
                "\nlibtorrent no esta instalado. Ejecuta: pip install libtorrent"
            )
        else:
            print(
                "\nNota: lamovie.org no es soportado por yt-dlp. "
                "Usa los enlaces de arriba (torrent con qBittorrent, "
                "o JDownloader 2 para mediafire/mega/1fichier)."
            )
        return

    if args.gui or (not args.url and len(sys.argv) == 1):
        root = tk.Tk()
        app = DownloaderUI(root)
        root.mainloop()
        return

    if not args.url:
        parser.print_help()
        sys.exit(1)

    check_yt_dlp()

    is_playlist = args.playlist
    archive_file = None if args.no_skip else "downloads/downloaded.txt"
    cookies_file = args.cookies

    try:
        if is_playlist:
            if args.type == "mp3":
                output = args.output or "downloads/mp3"
                download_playlist_mp3(args.url, output, args.quality, archive_file, cookies_file)
            else:
                output = args.output or "downloads/video"
                download_playlist_video(args.url, output, args.quality, archive_file, cookies_file)
        else:
            if args.type == "mp3":
                output = args.output or "downloads/mp3"
                download_mp3(args.url, output, args.quality, archive_file, cookies_file)
            else:
                output = args.output or "downloads/video"
                download_video(args.url, output, args.quality, archive_file, cookies_file)

        print("\nDescarga completada exitosamente!")

    except subprocess.CalledProcessError as e:
        print(f"\nError durante la descarga: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nDescarga cancelada por el usuario.")
        sys.exit(0)


if __name__ == "__main__":
    main()
