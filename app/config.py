from __future__ import annotations

from pathlib import Path
import json
import os
import sys


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "YouTuber Downloader"
        return Path.home() / "AppData" / "Local" / "YouTuber Downloader"
    return Path(__file__).resolve().parents[1]


BASE_DIR = _base_dir()
ENV_PATH = BASE_DIR / ".env"
USER_SETTINGS_PATH = BASE_DIR / "data" / "settings.json"
SUPABASE_PROJECT_URL = "https://bdzprzrnxzhgwswmlyxk.supabase.co"


def get_language() -> str:
    if not USER_SETTINGS_PATH.exists():
        return "es"
    settings = json.loads(USER_SETTINGS_PATH.read_text(encoding="utf-8"))
    language = settings.get("language", "es")
    return language if language in {"es", "en-US"} else "es"


def get_country_analytics_enabled() -> bool:
    if not USER_SETTINGS_PATH.exists():
        return False
    settings = json.loads(USER_SETTINGS_PATH.read_text(encoding="utf-8"))
    return settings.get("country_analytics_enabled", False) is True


def save_country_analytics_enabled(enabled: bool) -> None:
    if not isinstance(enabled, bool):
        raise ValueError("Country analytics preference must be a boolean")
    settings = {}
    if USER_SETTINGS_PATH.exists():
        settings = json.loads(USER_SETTINGS_PATH.read_text(encoding="utf-8"))
    USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings["country_analytics_enabled"] = enabled
    USER_SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_language(language: str) -> None:
    if language not in {"es", "en-US"}:
        raise ValueError(f"Unsupported language: {language}")
    settings = {}
    if USER_SETTINGS_PATH.exists():
        settings = json.loads(USER_SETTINGS_PATH.read_text(encoding="utf-8"))
    USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings["language"] = language
    USER_SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


ENV_VALUES = _read_env_file()


def get_setting(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is not None:
        return value
    return ENV_VALUES.get(name, default)


def downloads_dir() -> str:
    configured = get_setting("DOWNLOADS_DIR", "downloads/video_lab")
    path = BASE_DIR / configured
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
