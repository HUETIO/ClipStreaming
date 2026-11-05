# Descarga de contenido de lamovie.org

## API oficial del sitio (recomendado)

lamovie.org es una SPA (Vue) que obtiene los datos de una API JSON propia:
`https://lamovie.org/wp-api/v1` (definida en `window.siteConfig.fastApi`).

### 1. Obtener metadatos del contenido

```
GET https://lamovie.org/wp-api/v1/single/<postType>?slug=<slug>&postType=<postType>
```

- `postType`: `movies` (de `/peliculas/`), `tvshows` (de `/series/`), `animes`, `novels`, `wwe`
- Ejemplo: `https://lamovie.org/wp-api/v1/single/movies?slug=don-q-2024&postType=movies`
- Retorna: `_id`, `title`, `overview`, `imdb_rating`, `release_date`, `runtime`, etc.

### 2. Obtener players y descargas

```
GET https://lamovie.org/wp-api/v1/player?postId=<_id>&demo=0
```

- Retorna `embeds[]` (vimeos.net, hlswish.com, voe.sx, filemoon.sx, videoapp.zip)
  y `downloads[]` (magnet, mediafire, mega, 1fichier).

### Implementado en el proyecto

- `lamovie.py`: resolvedor de la API (`resolve_lamovie(url)`) con tests.
- `youtube_downloader.py`: detecta URLs de lamovie.org, resuelve los enlaces
  y guarda un Markdown con players y descargas (CLI y GUI).
- `markdown_utils.py --markdown` también enriquece páginas de lamovie.org.

### Herramientas para los enlaces resultantes

- **magnet:** qBittorrent / Transmission
- **mediafire / mega / 1fichier:** JDownloader 2
- **voe.sx:** yt-dlp lo soporta, pero muchos videos están borrados (404)
- **vimeos.net / videoapp.zip / hlswish.com:** no soportados por yt-dlp
- **filemoon.sx:** bloqueado explícitamente por yt-dlp (piratería)

## Situación actual

lamovie.org no es soportado por yt-dlp. El extractor genérico no puede obtener el video.

## Opciones para descargar

### 1. yt-dlp con extractor personalizado

Crear un extractor personalizado para lamovie.org:

```python
# lamovie_extractor.py
from yt_dlp.extractor.common import InfoExtractor

class LamovieIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?lamovie\.org/peliculas/(?P<id>[^/]+)/?'
    
    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        
        # Buscar URL del video en el HTML
        # Esto requiere analizar la estructura del sitio
        formats = self._extract_m3u8_formats(
            self._search_regex(r'(https?://[^\s]+\.m3u8)', webpage, 'm3u8 url'),
            video_id, 'mp4'
        )
        
        return {
            'id': video_id,
            'title': self._og_search_title(webpage),
            'formats': formats,
        }
```

### 2. Usar playwright/selenium para extraer la URL del video

```python
from playwright.sync_api import sync_playwright

def get_video_url(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        
        # Buscar el elemento de video
        video = page.query_selector('video source')
        if video:
            return video.get_attribute('src')
        
        # Buscar en scripts
        scripts = page.query_selector_all('script')
        for script in scripts:
            content = script.inner_text()
            if 'm3u8' in content or 'mp4' in content:
                # Extraer URL con regex
                import re
                urls = re.findall(r'https?://[^\s"\']+\.(?:m3u8|mp4)', content)
                if urls:
                    return urls[0]
        
        browser.close()
    return None
```

### 3. Usar JDownloader 2

JDownloader 2 tiene soporte para muchos sitios de streaming:

1. Descargar JDownloader 2 desde https://jdownloader.org/
2. Copiar la URL de lamovie.org
3. JDownloader detectará automáticamente el video
4. Descargar directamente

### 4. Usar youtube-dl con cookies y user-agent

```bash
yt-dlp --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
       --referer "https://lamovie.org/" \
       --add-header "Accept-Language:es-ES,es;q=0.9" \
       -f best \
       -o "downloads/%(title)s.%(ext)s" \
       "https://lamovie.org/peliculas/las-mejores-2026/"
```

### 5. Usar streamlink

```bash
pip install streamlink
streamlink "https://lamovie.org/peliculas/las-mejores-2026/" best -o video.mp4
```

### 6. Usar ffmpeg directamente (si obtienes la URL del video)

```bash
ffmpeg -i "URL_DEL_VIDEO" -c copy output.mp4
```

## Estructura típica de sitios de streaming

Estos sitios suelen usar:

- **Video.js** o **Player.js** como reproductor
- **HLS (m3u8)** o **MP4** como formato
- **URLs firmadas** que expiran en el tiempo
- **Protección con tokens** o cookies

## Pasos para analizar el sitio

1. Abrir DevTools (F12) en el navegador
2. Ir a la pestaña "Network"
3. Filtrar por "media" o "m3u8"
4. Reproducir el video
5. Copiar la URL del video que aparece en las peticiones

## Solución recomendada

La opción más robusta es crear un extractor personalizado para yt-dlp o usar JDownloader 2.
