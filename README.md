# Clipstream

Tu contenido, siempre a un clic.

A desktop media downloader built with Python + Flet and `yt-dlp`.

## Project structure

- `main.py` - application bootstrap
- `app/` - application configuration, media downloading, and UI
- `app/presentation/` - Flet shell, settings, video lab, and shared UI components
- `data/` - runtime data files
- `downloads/` - generated outputs
- `lamovie.py`, `markdown_utils.py`, and `abrir_torrent_descargar.py` - reusable services exposed in the Flet app

## Run

On Windows, run `run_app.bat`. The launcher detects compatible 64-bit Python
3.10-3.13 installations, creates a version-specific virtual environment, and
installs the pinned dependencies from `requirements.txt`. If no compatible
Python is found, it can install Python 3.13 through `winget`; reopen the
launcher after that installation. Python itself must be installed separately
from the project files when `winget` is unavailable.

Choose option 1 in the launcher to create the standalone portable executable
at `dist/portable/Clipstream.exe` and the Windows installer at
`dist/installer/Clipstream-Setup.exe`. This requires Inno Setup 6; the
launcher offers to install it with `winget` if it is not already available.
Packaged builds keep settings and downloads under
`%LOCALAPPDATA%\YouTuber Downloader` to preserve existing user data.

For manual installation, use a compatible Python version explicitly:

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 main.py
```

The Flet app uses the yt-dlp service in `app/infrastructure/video/video_lab.py`
for real downloads; it supports single videos and playlists, MP4/MKV, MP3,
progress reporting, cookies, and browser sessions. The separate
`youtube_downloader.py` and `all_download.py` scripts contain legacy command-line
and desktop entry points for overlapping yt-dlp functionality.

## Features

- Color-themed Flet interface with Video Lab as the starting screen and a settings page
- Configurable interface language: Spanish or English (United States), with the choice saved between launches
- Lamovie link resolution, web-page-to-Markdown export, and torrent download screens are available from the navigation rail.
- Torrent downloads require `libtorrent`; the Flet screen accepts magnet links or `.torrent` files and shows download percentage, transfer rates, peers, ETA, and tracker/network logs. Magnet metadata lookup times out with a diagnostic if no peers provide the metadata.
- Video Lab supports a multi-URL download queue with per-link progress states, removal of pending links, and cleanup of finished items.
- Video Lab supports single videos and playlists, MP4/MKV video or MP3 audio, quality selection, output-folder selection, download archives to skip previously downloaded items, and optional cookies-file or browser-session authentication.
- yt-dlp verbose diagnostics are shown in Video Lab, with the latest 200 debug lines retained for troubleshooting.
- The footer shows the connection country (country code only). Optional country usage statistics can be enabled in Settings and are off by default.

## Optional country statistics

To enable the feature for your Supabase project:

1. Install the Supabase CLI and authenticate locally with `supabase login`.
2. Link this workspace to the project with `supabase link --project-ref bdzprzrnxzhgwswmlyxk`. The CLI prompts for the database password; do not put that password in `.env` or commit it.
3. Apply the migration with `supabase db push --remote`.
4. Restart the app and turn on **Share anonymous country statistics** in Settings to send opt-in usage counts.

The app is configured with this project's URL and publishable key. For local development, these can be overridden with `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in `.env`; a publishable key is intended for desktop apps, but never use a Supabase secret key here. The SQL for manually applying the schema is also available in [`supabase/setup_country_analytics.sql`](supabase/setup_country_analytics.sql).

To show the country in the footer, the app contacts `api.country.is`, which processes the public IP to return a country code. This country lookup occurs regardless of the statistics opt-in. The app does not display, store, or send the IP to Supabase; Supabase receives only country code and app version when the user has enabled usage statistics. Supabase's request infrastructure may still process connection metadata. The `app_usage_events` table is insert-only for the app's public role. To see counts in Supabase's SQL Editor, run:

```sql
select country_code, app_version, count(*) as app_starts
from public.app_usage_events
group by country_code, app_version
order by app_starts desc;
```

These are opt-in app-start counts, not unique people or installations, and public clients can tamper with submitted country codes.

## Optional Google account

The app remains usable as a guest. To enable **Continue with Google**:

1. In Google Cloud, configure the OAuth consent screen and create an OAuth client ID of type **Web application**.
2. Add this authorized redirect URI in Google Cloud: `https://bdzprzrnxzhgwswmlyxk.supabase.co/auth/v1/callback`.
3. In Supabase, open **Authentication → Sign In / Providers → Google**, enable Google, and enter the Google client ID and client secret. Keep the client secret only in the Supabase Dashboard; never put it in the app or `.env`.
4. In Supabase **Authentication → URL Configuration → Redirect URLs**, allow `http://127.0.0.1:8765/auth/callback/**`.
5. Restart Clipstream and choose **Continue with Google** in Settings. The sign-in uses PKCE and opens the system browser. The refresh token is stored in the Windows credential store; it is not written to `settings.json`.

The first account release provides optional Google sign-in and sign-out only. Download history and settings are not synchronized between devices yet; those account features need a separate data model and migration.

## Vimeo

- URLs in the form `vimeo.com/<id>` are normalized to `player.vimeo.com/video/<id>`, which allows public videos to download without login or cookies.
- Private, password-protected, or members-only videos require a valid session. Use a Netscape-format cookies file with real values exported by "Get cookies.txt LOCALLY" while logged in to Vimeo, or use Firefox browser cookies.
- Edge/Chrome cookie exports containing `<ABE>` placeholders do not contain usable cookie values and are rejected.
- Video Lab can download MP4 and MP3 in one operation; it prefers H.264 video when available for broader playback compatibility.

## TikTok downloads

TikTok's `Unexpected response from webpage request` error is currently an upstream yt-dlp extractor issue, not an application or Flet error. See [yt-dlp issue #17604](https://github.com/yt-dlp/yt-dlp/issues/17604). Updating yt-dlp or supplying cookies may not resolve it until the extractor is fixed upstream. Video Lab displays the failure in the app instead of writing yt-dlp's raw error to the console.
