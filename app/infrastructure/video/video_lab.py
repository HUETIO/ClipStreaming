from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, cast
from urllib.parse import parse_qs, urlsplit

import yt_dlp
from yt_dlp.utils import DownloadError


ProgressHook = Callable[[dict[str, Any]], None]
_VIMEO_ID_RE = re.compile(
    r"^https?://(?:www\.)?vimeo\.com/(?P<id>\d+)(?:/(?P<hash>[0-9A-Za-z]+))?(?:[?#].*)?$",
    re.IGNORECASE,
)
_VIMEO_PLAYER_RE = re.compile(
    r"^https?://player\.vimeo\.com/video/(?P<id>\d+)(?:[?#].*)?$",
    re.IGNORECASE,
)
_ABE_MARKERS = ("<ABE>", "<SIN-CLAVE>")
_ABE_COOKIES_MESSAGE = (
    'Selected cookies file cannot be used: it contains App-Bound Encryption '
    'placeholders (`<ABE>` / `<SIN-CLAVE>`) exported from Edge/Chrome, so the '
    'cookie values are missing. Re-export real values with the "Get cookies.txt '
    'LOCALLY" browser extension while logged in to the site, or use Firefox.'
)
_VIMEO_LOGIN_MESSAGE = (
    'This Vimeo video requires a logged-in session (private, password, or '
    'members-only). Public videos work without cookies. For private videos: '
    'log in to vimeo.com in your browser and export a Netscape cookies file with '
    '"Get cookies.txt LOCALLY", then select it in "Cookies file".'
)
_FORMAT_ERROR_MESSAGE = (
    "yt-dlp could not find a compatible format for this video. Check the URL and "
    "try a different quality. If it persists, update yt-dlp."
)
_COOKIE_DATABASE_ERROR_MESSAGE = (
    "The browser is using its cookie database. Close the browser completely and "
    "try again, or select a cookies file instead."
)


class _YtDlpLogger:
    def __init__(self, progress_hook: ProgressHook | None):
        self._progress_hook = progress_hook

    def debug(self, message: str) -> None:
        if self._progress_hook:
            self._progress_hook({"status": "debug", "message": message})

    def warning(self, message: str) -> None:
        if self._progress_hook:
            self._progress_hook({"status": "warning", "message": message})

    def error(self, message: str) -> None:
        if self._progress_hook:
            self._progress_hook({"status": "error", "message": message})


class VideoLab:
    def __init__(self, downloads_dir: str):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

    def download_video(
        self,
        url: str,
        quality: str = "best",
        output_format: str = "mp4",
        *,
        download_type: str = "video",
        is_playlist: bool = False,
        output_dir: str | None = None,
        skip_existing: bool = True,
        cookies_file: str | None = None,
        browser: str | None = None,
        progress_hook: ProgressHook | None = None,
    ) -> str:
        if not url or not url.startswith(("http://", "https://")):
            raise ValueError("Enter a valid http:// or https:// URL.")
        if download_type not in {"video", "mp3", "both"}:
            raise ValueError("Download type must be 'video', 'mp3', or 'both'.")
        if cookies_file and browser:
            raise ValueError("Choose a cookies file or a browser, not both.")
        if cookies_file:
            self._assert_usable_cookies(cookies_file)

        original_url = url
        normalized_url, _ = self.normalize_url(url)
        if normalized_url != url:
            original_url = url
        else:
            original_url = self._vimeo_page_url(url) or url

        destination = Path(output_dir) if output_dir else self.downloads_dir
        destination.mkdir(parents=True, exist_ok=True)

        if download_type == "both":
            if progress_hook:
                progress_hook({"status": "debug", "message": "[1/2] Downloading MP4..."})
            video_dir = self._download_once(
                normalized_url,
                original_url,
                quality,
                output_format,
                download_type="video",
                is_playlist=is_playlist,
                destination=destination,
                skip_existing=skip_existing,
                cookies_file=cookies_file,
                browser=browser,
                progress_hook=progress_hook,
            )
            if progress_hook:
                progress_hook({"status": "debug", "message": "[2/2] Extracting MP3..."})
            try:
                mp3_dir = self._download_once(
                    normalized_url,
                    original_url,
                    "192",
                    output_format,
                    download_type="mp3",
                    is_playlist=is_playlist,
                    destination=destination,
                    skip_existing=skip_existing,
                    cookies_file=cookies_file,
                    browser=browser,
                    progress_hook=progress_hook,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"MP4 downloaded successfully, but MP3 extraction failed: {exc}"
                ) from exc
            return f"MP4: {video_dir}; MP3: {mp3_dir}"

        return self._download_once(
            normalized_url,
            original_url,
            quality,
            output_format,
            download_type=download_type,
            is_playlist=is_playlist,
            destination=destination,
            skip_existing=skip_existing,
            cookies_file=cookies_file,
            browser=browser,
            progress_hook=progress_hook,
        )

    @staticmethod
    def normalize_url(url: str) -> tuple[str, str]:
        """Return a normalized media URL and its platform name."""
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        is_vimeo = hostname == "vimeo.com" or hostname.endswith(".vimeo.com")
        if not is_vimeo:
            return url, "otro"

        match = _VIMEO_ID_RE.fullmatch(url)
        if match:
            video_hash = match.group("hash")
            player_url = f"https://player.vimeo.com/video/{match.group('id')}"
            if video_hash:
                player_url += f"?h={video_hash}"
            return player_url, "vimeo"

        return url, "vimeo"

    @staticmethod
    def _vimeo_page_url(url: str) -> str | None:
        match = _VIMEO_PLAYER_RE.fullmatch(url)
        if not match:
            return None
        page_url = f"https://vimeo.com/{match.group('id')}"
        video_hash = parse_qs(urlsplit(url).query).get("h", [None])[0]
        if video_hash:
            page_url += f"/{video_hash}"
        return page_url

    @staticmethod
    def _assert_usable_cookies(cookies_file: str) -> None:
        content = Path(cookies_file).read_text(encoding="utf-8", errors="replace")

        def contains_marker(value: Any) -> bool:
            if isinstance(value, str):
                return any(marker in value for marker in _ABE_MARKERS)
            if isinstance(value, dict):
                return any(contains_marker(item) for item in value.values())
            if isinstance(value, list):
                return any(contains_marker(item) for item in value)
            return False

        for line in content.splitlines():
            fields = line.split("\t")
            if len(fields) >= 7 and contains_marker(fields[6]):
                raise ValueError(_ABE_COOKIES_MESSAGE)

        try:
            json_value = json.loads(content)
        except json.JSONDecodeError:
            return
        if contains_marker(json_value):
            raise ValueError(_ABE_COOKIES_MESSAGE)

    def _download_once(
        self,
        url: str,
        original_url: str,
        quality: str,
        output_format: str,
        *,
        download_type: str,
        is_playlist: bool,
        destination: Path,
        skip_existing: bool,
        cookies_file: str | None,
        browser: str | None,
        progress_hook: ProgressHook | None,
    ) -> str:
        media_dir = destination / ("mp3" if download_type == "mp3" else "video")
        media_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            "%(playlist_title)s/%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"
            if is_playlist
            else "%(title)s [%(id)s].%(ext)s"
        )
        options: dict[str, Any] = {
            "format": self._format_selector(quality, download_type),
            "outtmpl": str(media_dir / filename),
            "ignoreerrors": is_playlist,
            "noplaylist": not is_playlist,
            "quiet": True,
            "no_warnings": True,
            "verbose": True,
            "logger": _YtDlpLogger(progress_hook),
        }

        if skip_existing:
            options["download_archive"] = str(media_dir / "downloaded.txt")
        if cookies_file:
            options["cookiefile"] = cookies_file
        if browser:
            options["cookiesfrombrowser"] = (browser,)
        if progress_hook:
            options["progress_hooks"] = [progress_hook]

        if download_type == "mp3":
            options["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": quality,
                }
            ]
        else:
            if output_format not in {"mp4", "mkv"}:
                raise ValueError("Output format must be 'mp4' or 'mkv'.")
            options["merge_output_format"] = output_format

        try:
            with yt_dlp.YoutubeDL(cast(Any, options)) as downloader:
                try:
                    result = downloader.extract_info(url, download=True)
                except DownloadError as exc:
                    message = str(exc)
                    if (
                        cookies_file
                        and original_url != url
                        and self._should_retry_vimeo_with_cookies(message)
                    ):
                        result = downloader.extract_info(original_url, download=True)
                    else:
                        self._raise_friendly_download_error(exc, original_url)
        except DownloadError as exc:
            self._raise_friendly_download_error(exc, original_url)

        if result is None and "tiktok.com" in original_url.lower():
            raise RuntimeError(
                "TikTok did not provide video information. The site may be temporarily "
                "blocking access or the video may be unavailable to yt-dlp. Retry later."
            )
        if result is None:
            raise RuntimeError("yt-dlp did not return download information.")

        return str(media_dir)

    @staticmethod
    def _should_retry_vimeo_with_cookies(message: str) -> bool:
        lowered = message.lower()
        return any(
            marker in lowered
            for marker in ("no video formats found", "password", "only works when logged-in")
        )

    @staticmethod
    def _raise_friendly_download_error(exc: DownloadError, url: str) -> None:
        message = str(exc)
        lowered = message.lower()
        if "tiktok.com" in url.lower() and "unexpected response" in lowered:
            raise RuntimeError(
                "TikTok is currently returning a webpage response that yt-dlp "
                "cannot process. This is a known upstream extractor issue "
                "(https://github.com/yt-dlp/yt-dlp/issues/17604), also reproduced "
                "with a nightly build. Cookies or updating yt-dlp may not fix it; "
                "retry after the upstream project releases a fix."
            ) from exc
        if "only works when logged-in" in lowered:
            raise RuntimeError(_VIMEO_LOGIN_MESSAGE) from exc
        if "requested format is not available" in lowered:
            raise RuntimeError(_FORMAT_ERROR_MESSAGE) from exc
        if "could not copy" in lowered and "cookie database" in lowered:
            raise RuntimeError(_COOKIE_DATABASE_ERROR_MESSAGE) from exc
        raise exc

    @staticmethod
    def _format_selector(quality: str, download_type: str = "video") -> str:
        if download_type == "mp3":
            return "bestaudio/best"

        caps = {
            "best": "",
            "1080": "[height<=1080]",
            "720": "[height<=720]",
            "480": "[height<=480]",
            "360": "[height<=360]",
        }
        if quality.lower() == "worst":
            return "worstvideo+worstaudio/worst"
        cap = caps.get(quality.lower(), "")
        return (
            f"bestvideo[ext=mp4][vcodec^=avc1]{cap}+bestaudio/"
            f"bestvideo[ext=mp4]{cap}+bestaudio/"
            f"bestvideo{cap}+bestaudio/"
            f"best[ext=mp4]{cap}/best"
        )
