from __future__ import annotations

import re

import requests

from app.config import (
    SUPABASE_PROJECT_URL,
    get_setting,
)


APP_VERSION = "1.0.0"
COUNTRY_LOOKUP_URL = "https://api.country.is/"
ANALYTICS_TABLE = "app_usage_events"
class UsageAnalyticsError(Exception):
    pass


def record_country_usage() -> str:
    country_code = lookup_country_code()
    return record_country_usage_for_country(country_code)


def lookup_country_code() -> str:
    try:
        country_response = requests.get(COUNTRY_LOOKUP_URL, timeout=5)
        country_response.raise_for_status()
        country_payload = country_response.json()
    except (requests.RequestException, ValueError) as exc:
        raise UsageAnalyticsError(
            "Could not determine the country from the public IP address."
        ) from exc

    if not isinstance(country_payload, dict):
        raise UsageAnalyticsError("The country lookup returned an invalid response.")
    country_code = country_payload.get("country")
    if not isinstance(country_code, str) or not re.fullmatch(
        r"[A-Z]{2}", country_code
    ):
        raise UsageAnalyticsError("The country lookup returned an invalid country code.")
    return country_code


def record_country_usage_for_country(country_code: str) -> str:
    supabase_url = get_setting("SUPABASE_URL", SUPABASE_PROJECT_URL)
    publishable_key = get_setting("SUPABASE_PUBLISHABLE_KEY")
    if not supabase_url or not publishable_key:
        raise UsageAnalyticsError(
            "Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in the local .env file."
        )

    if not isinstance(country_code, str) or not re.fullmatch(
        r"[A-Z]{2}", country_code
    ):
        raise UsageAnalyticsError("The country lookup returned an invalid country code.")

    try:
        response = requests.post(
            f"{supabase_url.rstrip('/')}/rest/v1/{ANALYTICS_TABLE}",
            headers={
                "apikey": publishable_key,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={
                "country_code": country_code,
                "app_version": APP_VERSION,
            },
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise UsageAnalyticsError(
            "Could not save the usage statistic to Supabase."
        ) from exc

    return country_code
