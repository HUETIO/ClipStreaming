# Especificación: Video Lab — Vimeo + descarga MP4 + MP3

Documento para el agente que implemente las modificaciones del aplicativo Flet
(`Architecture Studio`). Todo lo que sigue está **verificado empíricamente**
contra `yt-dlp 2026.08.19`, `ffmpeg 9.0.2` y el video de prueba
`https://vimeo.com/1228694119` ("Anonymity - Maison Margiela FW27", 141 s,
1080p, HLS).

---

## 1. Diagnóstico (causas raíz, no reimplementar)

| # | Hallazgo verificado | Consecuencia para la app |
|---|---|---|
| 1 | El extractor `web` de Vimeo exige sesión (`REQUIRES_AUTH: True`). yt-dlp lanza `The web client only works when logged-in` para `vimeo.com/<id>` sin cookies válidas. | Las URLs `vimeo.com/<id>` fallan si se envían tal cual. |
| 2 | La URL del reproductor **no** exige login: `https://player.vimeo.com/video/<id>` extrae los formatos HLS sin cookies. Verificado con el video de prueba. | **Solución principal:** normalizar toda URL `vimeo.com/<id>` → `player.vimeo.com/video/<id>`. |
| 3 | Las cookies exportadas de Edge/Chrome por `D:\DASH.IO\COOKIES_EXTRACTOR` tienen los valores reemplazados por los marcadores `<ABE>` (App-Bound Encryption, cookie v20) y `<SIN-CLAVE>`; solo metadatos, ningún valor real. Un archivo con cookie `vimeo=<ABE>` hace que yt-dlp crea que hay login y falle peor. | Validar el archivo de cookies antes de usarlo y rechazar marcadores. |
| 4 | `--cookies-from-browser chrome/edge` falla doblemente: base de datos bloqueada si el navegador está abierto (`Could not copy Chrome cookie database`) y cookies ABE ilegibles. Solo Firefox es fiable. | Advertir en la UI y mapear el error a mensaje amigable. |
| 5 | **Bug actual del selector de formato:** el selector `"best"` del código es `bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best`. En Vimeo **no existe** ningún formato `ext=m4a` (el audio HLS tiene `ext=mp4`) y ningún formato single-file con audio+video, y `best[ext=mp4]`/`best` solo aceptan formatos con ambas pistas → yt-dlp responde `Requested format is not available`. **El Video Lab actual NO puede descargar Vimeo aunque se le pase la URL del player.** | Reescribir el selector (ver §3.2). |
| 6 | `bestvideo` solo (sin restricción de códec) elige AV1 (`av01`, 2693k) sobre H.264 (`avc1`, 5499k) en Vimeo. AV1-in-MP4 no se reproduce en Windows Media Player clásico, TVs y editores. | Preferir `vcodec^=avc1` con fallback. |
| 7 | yt-dlp avisa `no impersonate target is available` sin `curl_cffi`; la impersonation TLS es requerida por Vimeo (web) y TikTok. | Añadir `curl_cffi` a `requirements.txt`. |
| 8 | El flujo actual solo permite un resultado por descarga (`video` **o** `mp3`). | Añadir tipo `both` (dos pasadas secuenciales, ver §3.3). |

---

## 2. Archivos a modificar

- `app/infrastructure/video/video_lab.py` — lógica de descarga (§3)
- `app/presentation/app.py` — UI de Video Lab (§4)
- `requirements.txt` — dependencias (§5)
- `README.md` — sección Vimeo (§5)

No tocar: CRUD, Dashboard, Settings, `app/domain/`, `app/infrastructure/data_sources/`,
el extractor de cookies externo ni `youtube_downloader.py` (GUI legacy aparte).

---

## 3. `app/infrastructure/video/video_lab.py`

### 3.1 Normalización de URLs de Vimeo (nuevo método público)

```python
import re

_VIMEO_ID_RE = re.compile(
    r"^https?://(?:www\.)?vimeo\.com/(?P<id>\d+)(?:/(?P<hash>[0-9A-Za-z]+))?(?:[?#].*)?$",
    re.IGNORECASE,
)

@staticmethod
def normalize_url(url: str) -> tuple[str, str]:
    """Devuelve (url_normalizada, plataforma)."""
```

Reglas:

| Entrada | Salida |
|---|---|
| `https://vimeo.com/1228694119` | `https://player.vimeo.com/video/1228694119` |
| `https://www.vimeo.com/1228694119` | `https://player.vimeo.com/video/1228694119` |
| `https://vimeo.com/1228694119/AbCdEf123` (no listado) | `https://player.vimeo.com/video/1228694119?h=AbCdEf123` |
| `https://vimeo.com/1228694119?text=1` | `https://player.vimeo.com/video/1228694119` (query salvo `h` se descarta) |
| `https://player.vimeo.com/video/1228694119` | sin cambio |
| `https://vimeo.com/channels/staffpicks/123`, `showcase`, `album`, `groups` | **sin cambio** (no aplica el player; requieren cookies reales) |
| Cualquier otra URL | sin cambio |

- `plataforma` = `"vimeo"` si la URL original matchea `vimeo.com`, si no `"otro"`.
- La normalización se aplica **siempre** al inicio de `download_video()`, antes de construir las opciones.
- **Fallback:** si la extracción con URL del player falla (`No video formats found`,
  `password`, o error de login) **y** el usuario definió `cookies_file`, reintentar
  una sola vez con la URL original `vimeo.com/<id>` + cookies. Si el reintento
  falla, propagar el error del reintento.

### 3.2 Selector de formato corregido (bug crítico §1.5)

Reemplazar `_format_selector` por:

```python
@staticmethod
def _format_selector(quality: str, download_type: str = "video") -> str:
    if download_type == "mp3":
        return "bestaudio/best"

    caps = {
        "best": "",
        "1080": "[height<=1080]",
        "720":  "[height<=720]",
        "480":  "[height<=480]",
        "360":  "[height<=360]",
    }
    if quality == "worst":
        return "worstvideo+worstaudio/worst"
    cap = caps.get(quality.lower(), "")
    return (
        f"bestvideo[ext=mp4][vcodec^=avc1]{cap}+bestaudio/"  # H.264: máxima compatibilidad
        f"bestvideo[ext=mp4]{cap}+bestaudio/"                 # mp4 con cualquier códec
        f"bestvideo{cap}+bestaudio/"                          # mejor video+audio, cualquier ext
        f"best{cap}/best"                                     # single-file de respaldo
    )
```

Obligaciones de este selector:

- **Nunca** filtrar audio por `[ext=m4a]` (Vimeo entrega audio `ext=mp4`; YouTube sí tiene m4a — el filtro sobra en cualquier caso).
- `bestaudio/best` funciona en Vimeo: elige `hls-...-audio-high-English`.
- Verificación obligatoria (debe imprimir un par `video+audio` sin error):
  ```bat
  python -m yt_dlp --simulate --no-playlist --print "%(format_id)s" -f "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio/bestvideo[ext=mp4]+bestaudio/bestvideo+bestaudio/best[ext=mp4]/best" "https://player.vimeo.com/video/1228694119"
  ```
  Resultado esperado: `hls-fastly_skyfire-5499+hls-fastly_skyfire-audio-high-English` (avc1 1080p + audio).

### 3.3 Nuevo tipo de descarga `both` (MP4 + MP3)

- Aceptar `download_type ∈ {"video", "mp3", "both"}` (validación al inicio).
- `both` = **dos pasadas secuenciales**, reutilizando la misma función:
  1. pasada `download_type="video"` → `downloads/video/`
  2. pasada `download_type="mp3"` (calidad de audio fija `192`) → `downloads/mp3/`
- Implementación recomendada: extraer el cuerpo actual a un método privado
  `_download_once(..., download_type: str, ...)` y que `download_video()` orqueste:
  para `both` llama `_download_once("video")` y luego `_download_once("mp3")`.
- **Archivos de archivo (skip existing) independientes por pasada:**
  `video/downloaded.txt` y `mp3/downloaded.txt` — así una re-ejecución retoma la
  pasada que faltó sin repetir la completada.
- Empezar cada pasada con un evento de progreso:
  `progress_hook({"status": "debug", "message": "[1/2] Downloading MP4..."})` / `"[2/2] Extracting MP3..."`.
- **Fallo parcial:** si la pasada 1 falla → propagar el error normal. Si la 1
  termina bien y la 2 falla → `raise RuntimeError(f"MP4 downloaded successfully, but MP3 extraction failed: {exc}")`.

### 3.4 Validación del archivo de cookies (nuevo)

```python
_ABE_MARKERS = ("<ABE>", "<SIN-CLAVE>")

@staticmethod
def _assert_usable_cookies(cookies_file: str) -> None:
    """Rechaza exportaciones Edge/Chrome cuyos valores son marcadores ABE."""
```

- Leer el archivo en texto (UTF-8 tolerante, `errors="replace"`), partir por líneas,
  y si **cualquier** campo de valor (columna 7 de Netscape, tab-separada) o valor
  JSON visible contiene `<ABE>` o `<SIN-CLAVE>` → `ValueError` con el mensaje
  exacto de §6.1.
- Llamarlo en `download_video()` cuando `cookies_file` esté definido, **antes** de
  construir opciones (falla rápido, sin hilos).

### 3.5 Mapeo de errores a mensajes amigables

En el bloque `except DownloadError`, además del caso TikTok existente:

| Condición (sobre `str(exc)`) | Mensaje nuevo |
|---|---|
| `"only works when logged-in"` | §6.2 |
| `"Requested format is not available"` | §6.3 |
| `"Could not copy"` y `"cookie database"` | §6.4 |

La validación ABE (§3.4) se lanza como `ValueError` antes del `try` de yt-dlp.

---

## 4. `app/presentation/app.py` (UI Video Lab)

1. **Dropdown Media** — añadir como **primera** opción:
   ```python
   ft.dropdown.Option("both", "Video (MP4) + Audio (MP3)"),
   ```
   (mantener `video` y `mp3`).
2. **`_on_download_type_change`** — para `both`: opciones de calidad de **video**
   (`best/1080/720/480/360/worst`, valor `best`), `format_drop` habilitado; el
   bitrate MP3 se fija internamente en `192` (no exponerlo en `both`).
3. **`run_video_download`**:
   - Antes de lanzar: `normalized, platform = VideoLab.normalize_url(url)` y mostrar
     `self.video_status.value = f"Detected: {platform} → {normalized}"` (la URL
     normalizada es la que se pasa a `download_video`).
   - Validar cookies en el hilo de UI: si `cookies_file` está definido, llamar
     `VideoLab._assert_usable_cookies(cookies_file)` dentro de `try/except ValueError`
     → `self._show_message(str(exc), ft.Colors.RED_200)` y `return` (sin lanzar hilo).
   - Paso `download_type=self.download_type_drop.value` (acepta `"both"`).
   - `except RuntimeError as exc:` — si el mensaje contiene
     `"MP4 downloaded successfully, but MP3 extraction failed"` mostrarlo en
     `video_status` y snackbar **naranja** (`ft.Colors.AMBER_200`); el resto de
     errores igual que hoy (rojo).
4. **Textos de ayuda** (conteo exacto, actualizar):
   - URL field: `hint_text="https://www.youtube.com/... | https://vimeo.com/123456789"`.
   - Cookies field: `hint_text="Netscape .txt with real values (not <ABE>)"`.
   - Bajo `browser_drop`, añadir un `ft.Text(..., size=12, color=ft.Colors.GREY_700)`
     con §6.5.
5. **Playlist button:** sin cambios; las URLs no normalizables (showcase/channels)
   pasan tal cual y su error cae en §3.5/§6.2.

---

## 5. Dependencias y docs

`requirements.txt` (agregar línea):

```
curl_cffi>=0.14.0
```

> Habilita la impersonation TLS de yt-dlp (aviso `no impersonate target is
> available`); requerida por Vimeo web y TikTok. Ya está instalada en el entorno
> actual (0.16.3), pero debe quedar declarada.

`README.md` — añadir sección **Vimeo**:

- URLs `vimeo.com/<id>` se convierten automáticamente a `player.vimeo.com/video/<id>`
  (no requiere login ni cookies para videos públicos).
- Videos privados/membresía: requieren cookies reales exportadas con la extensión
  "Get cookies.txt LOCALLY" (navegador con sesión iniciada en Vimeo) o Firefox.
- Cookies Edge/Chrome con marcador `<ABE>` no son usables.

---

## 6. Mensajes exactos (usar textualmente)

**6.1 Cookies ABE** (`ValueError`):

> Selected cookies file cannot be used: it contains App-Bound Encryption
> placeholders (`<ABE>` / `<SIN-CLAVE>`) exported from Edge/Chrome, so the
> cookie values are missing. Re-export real values with the "Get cookies.txt
> LOCALLY" browser extension while logged in to the site, or use Firefox.

**6.2 Vimeo login requerido** (`RuntimeError`):

> This Vimeo video requires a logged-in session (private, password, or
> members-only). Public videos work without cookies. For private videos:
> log in to vimeo.com in your browser and export a Netscape cookies file with
> "Get cookies.txt LOCALLY", then select it in "Cookies file".

**6.3 Formato no disponible** (`RuntimeError`):

> yt-dlp could not find a compatible format for this video. Check the URL and
> try a different quality. If it persists, update yt-dlp.

**6.4 DB de cookies bloqueada** (`RuntimeError`):

> The browser is using its cookie database. Close the browser completely and
> try again, or select a cookies file instead.

**6.5 Texto de ayuda bajo "Use browser session"**:

> Firefox works reliably. Chrome/Edge cookies are encrypted with App-Bound
> Encryption and usually cannot be read; prefer a cookies file.

---

## 7. Criterios de aceptación

Ejecutar **tras implementar** los cambios, en orden desde la raíz del proyecto (PowerShell):

1. **Selector sin error (regresión §1.5):**
   ```bat
   python -m yt_dlp --simulate --no-playlist --print "%(format_id)s" -f "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio/bestvideo[ext=mp4]+bestaudio/bestvideo+bestaudio/best[ext=mp4]/best" "https://player.vimeo.com/video/1228694119"
   ```
   → imprime `hls-fastly_skyfire-5499+hls-fastly_skyfire-audio-high-English`, sin `ERROR`.
   (El `WARNING: Failed to parse XML` de un probe HLS es benigno: otro CDN
   probeado responde HTML y yt-dlp continúa con el siguiente; no es un fallo.)
2. **Normalización:**
   ```bat
   python -c "from app.infrastructure.video.video_lab import VideoLab as V; print(V.normalize_url('https://vimeo.com/1228694119')); print(V.normalize_url('https://vimeo.com/1228694119/AbC123'))"
   ```
   → `https://player.vimeo.com/video/1228694119` y `...?h=AbC123`.
3. **Descarga end-to-end `both` (sin cookies):**
   ```bat
   python -c "from app.infrastructure.video.video_lab import VideoLab; VideoLab('downloads').download_video('https://vimeo.com/1228694119', quality='best', output_format='mp4', download_type='both')"
   ```
   → existen `downloads\video\Anonymity - Maison Margiela FW27 [1228694119].mp4`
   (≈45–92 MB, `ffprobe` confirma `1920x1080` y **acodec distinto de none**, es
   decir con audio) y `downloads\mp3\... [1228694119].mp3` (≈4 MB).
4. **Rechazo de cookies ABE:**
   ```bat
   python -c "from app.infrastructure.video.video_lab import VideoLab; VideoLab('downloads').download_video('https://vimeo.com/1228694119', cookies_file=r'D:\DASH.IO\COOKIES_EXTRACTOR\cookies_20261006_144844_netscape.txt')"
   ```
   → `ValueError` con el mensaje §6.1 **antes** de cualquier petición de red.
5. **YouTube no regresiona:** descarga `video` con calidad `best` de un video
   público de YouTube → formato `avc1`+`m4a` fusionado a mp4, sin
   `Requested format is not available`.
6. **UI:** `python main.py` → Video Lab muestra la opción
   "Video (MP4) + Audio (MP3)", el texto de ayuda ABE, la URL detectada en la
   barra de estado y la barra de progreso pasa por `[1/2]` → `[2/2]`.

---

## 8. Restricciones

- No modificar código de yt-dlp ni copiar sus extractores.
- No implementar login con usuario/contraseña ni `--video-password` (fuera de alcance).
- No descifrar cookies ABE: solo detectar y rechazar con mensaje.
- Mantener el contrato existente de `download_video(...)` (parámetros y retorno `str`);
  `download_type` es la única ampliación.
- Los mensajes de UI en inglés (la app está en inglés); este documento en español
  es solo para el agente.
