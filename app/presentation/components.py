from __future__ import annotations

import flet as ft


_ENGLISH_TO_SPANISH = {
    "Video Lab": "Laboratorio de video",
    "Lamovie": "Lamovie",
    "Web to Markdown": "Web a Markdown",
    "Torrent": "Torrent",
    "Settings": "Configuración",
    "DASH.IO": "DASH.IO",
    "Your content, always one click away.": "Tu contenido, siempre a un clic.",
    "STOP": "DETENER",
    "Stop": "Detener",
    "Stop download": "Detener descarga",
    "Stopping download...": "Deteniendo la descarga...",
    "Change theme": "Cambiar tema",
    "Video or playlist URL": "URL de video o lista",
    "https://youtube.com/... or https://vimeo.com/...": "https://youtube.com/... o https://vimeo.com/...",
    "Media type": "Tipo de contenido",
    "Video (MP4) + Audio (MP3)": "Video (MP4) + audio (MP3)",
    "Video only (MP4/MKV)": "Solo video (MP4/MKV)",
    "Audio only (MP3)": "Solo audio (MP3)",
    "Quality": "Calidad",
    "Best": "Mejor",
    "Worst": "Peor",
    "Container": "Formato",
    "Destination: ": "Destino: ",
    "Cookies file (optional)": "Archivo de cookies (opcional)",
    "Browser session (optional)": "Sesión del navegador (opcional)",
    "None": "Ninguno",
    "Microsoft Edge": "Microsoft Edge",
    "Skip videos already downloaded": "Omitir videos ya descargados",
    "Ready to download": "Listo para descargar",
    "yt-dlp diagnostics": "Diagnóstico de yt-dlp",
    "Show diagnostics": "Mostrar diagnóstico",
    "Hide diagnostics": "Ocultar diagnóstico",
    "Batch URLs": "URLs en lote",
    "Paste one video URL per line": "Pega una URL de video por línea",
    "pending": "pendientes",
    "Download video": "Descargar video",
    "Download playlist": "Descargar lista",
    "Add to queue": "Añadir a la cola",
    "Start queue": "Iniciar cola",
    "Retry failed": "Reintentar fallidos",
    "Clear finished": "Limpiar finalizados",
    "Download settings": "Configuración de descarga",
    "Choose a URL, format, quality and destination.": "Elige una URL, formato, calidad y destino.",
    "Browse": "Explorar",
    "Advanced: Authentication": "Avanzado: autenticación",
    "Optional cookies for private or restricted videos": "Cookies opcionales para videos privados o restringidos",
    "Select cookies": "Elegir cookies",
    "Choose either a cookies file or a browser session, not both. Firefox is recommended.": "Elige un archivo de cookies o una sesión del navegador, no ambos. Se recomienda Firefox.",
    "Download queue": "Cola de descargas",
    "Process multiple links sequentially.": "Procesa varios enlaces en secuencia.",
    "Queue": "Cola",
    "Video Lab": "Laboratorio de video",
    "Download media from YouTube, Vimeo and other supported sites.": "Descarga contenido de YouTube, Vimeo y otros sitios compatibles.",
    "Select a cookies file": "Selecciona un archivo de cookies",
    "Add at least one URL to the queue.": "Añade al menos una URL a la cola.",
    "Invalid URL: ": "URL no válida: ",
    ". Links must start with http:// or https://.": ". Los enlaces deben comenzar con http:// o https://.",
    "Waiting": "En espera",
    "Downloading": "Descargando",
    "Completed": "Completado",
    "Failed": "Error",
    "Stopped": "Detenido",
    "Downloading...": "Descargando...",
    "Remove from queue": "Quitar de la cola",
    "Add at least one URL before starting the queue.": "Añade al menos una URL antes de iniciar la cola.",
    "Queue stopped: ": "Cola detenida: ",
    "Queue finished: ": "Cola finalizada: ",
    "completed items": "completados",
    "failed items": "fallidos",
    "stopped items": "detenidos",
    "Enter a valid http:// or https:// URL.": "Introduce una URL http:// o https:// válida.",
    "Download stopped.": "Descarga detenida.",
    "Download failed: ": "Error al descargar: ",
    "Download complete: ": "Descarga completada: ",
    "Connecting to ": "Conectando con ",
    "Finalizing file...": "Finalizando archivo...",
    "Downloading: ": "Descargando: ",
    " s elapsed": " s transcurridos",
    " min remaining": " min restantes",
    " s remaining": " s restantes",
    "connections": "conexiones",
    "peers": "pares",
    "seeds": "semillas",
    "Downloading · ": "Descargando · ",
    "Waiting for metadata": "Esperando metadatos",
    "Looking for peers to retrieve metadata...": "Buscando peers para obtener metadatos...",
    "Looking up Lamovie...": "Consultando Lamovie...",
    "Could not resolve link: ": "No se pudo resolver el enlace: ",
    "Result: ": "Resultado: ",
    "Lamovie URL": "URL de Lamovie",
    "Enter a URL to resolve its links.": "Introduce una URL para resolver sus enlaces.",
    "Resolve links": "Resolver enlaces",
    "Resolve Lamovie": "Resolver Lamovie",
    "Look up title details and its playback and download links.": "Consulta los datos del título y sus enlaces de reproducción y descarga.",
    "Enter the Lamovie URL.": "Introduce la URL de Lamovie.",
    "Page URL": "URL de la página",
    "Output folder": "Carpeta de salida",
    "The content will be saved as a .md file.": "El contenido se guardará como un archivo .md.",
    "Convert and save": "Convertir y guardar",
    "Extract metadata and convert a web page to Markdown.": "Extrae metadatos y convierte el contenido de una página web a Markdown.",
    "Change folder": "Cambiar carpeta",
    "Select the Markdown folder": "Selecciona la carpeta de Markdown",
    "Downloading and converting the page...": "Descargando y convirtiendo la página...",
    "Could not create Markdown: ": "No se pudo generar el Markdown: ",
    "File saved: ": "Archivo guardado: ",
    "Magnet link": "Enlace magnet",
    "Download log": "Registro de descarga",
    "Ready to download.": "Preparado para descargar.",
    "Torrent downloads unavailable: install libtorrent to enable them.": "Descargas torrent no disponibles: instala libtorrent para habilitarlas.",
    "Start download": "Iniciar descarga",
    "Choose .torrent file": "Elegir archivo .torrent",
    "Torrent downloads": "Descargas Torrent",
    "Paste a magnet link or choose a .torrent file.": "Pega un magnet link o selecciona un archivo .torrent.",
    "Select a .torrent file": "Selecciona un archivo .torrent",
    "Paste a valid magnet link or choose an existing .torrent file.": "Pega un magnet link válido o selecciona un archivo .torrent existente.",
    "Torrent downloads unavailable: install libtorrent and restart the app.": "Descargas torrent no disponibles: instala libtorrent y reinicia la app.",
    "Connecting to the torrent network...": "Conectando con la red torrent...",
    "Download stopped by user.": "Descarga detenida por el usuario.",
    "Could not download torrent: ": "No se pudo descargar el torrent: ",
    "Incomplete": "No completada",
    "Download ": "Descarga ",
    "completed": "completada",
    "incomplete": "incompleta",
    "ETA unavailable": "ETA no disponible",
    "Set the download folder, language, and appearance.": "Configura la carpeta de destino, el idioma y la apariencia.",
    "Download folder": "Carpeta de descargas",
    "Destination folder": "Carpeta de destino",
    "Browse": "Explorar",
    "Current theme: ": "Tema actual: ",
    "Dark": "Oscuro",
    "Light": "Claro",
    "Dark mode": "Modo oscuro",
    "Language": "Idioma",
    "Choose the interface language.": "Selecciona el idioma de la interfaz.",
    "Spanish": "Español",
    "English (United States)": "Inglés (Estados Unidos)",
    "About": "Acerca de",
    "Appearance": "Apariencia",
    "Account": "Cuenta",
    "Guest": "Invitado",
    "Guest account": "Cuenta de invitado",
    "Country: ": "País: ",
    "Country: checking...": "País: consultando...",
    "Country unavailable.": "País no disponible.",
    "The app remains available in guest mode. Google sign-in is optional and prepares your account for future synced features.": "La aplicación sigue disponible como invitado. El acceso opcional con Google prepara tu cuenta para futuras funciones sincronizadas.",
    "Guest mode. No account is signed in.": "Modo invitado. No hay ninguna cuenta iniciada.",
    "Continue with Google": "Continuar con Google",
    "Sign out": "Cerrar sesión",
    "Waiting for Google sign-in...": "Esperando el acceso con Google...",
    "Could not sign in: ": "No se pudo iniciar sesión: ",
    "Could not restore account: ": "No se pudo restaurar la cuenta: ",
    "Signed in as: ": "Sesión iniciada como: ",
    "Could not sign out: ": "No se pudo cerrar sesión: ",
    "Usage statistics": "Estadísticas de uso",
    "Share anonymous country statistics": "Compartir estadísticas anónimas por país",
    "The footer estimates your country from your public IP using api.country.is. This service processes your IP to identify the country. When enabled, anonymous statistics send only your country code and app version to Supabase; your IP is never sent there.": "El pie de página estima tu país a partir de tu IP pública mediante api.country.is. Ese servicio procesa tu IP para identificar el país. Si activas las estadísticas anónimas, solo se envían a Supabase el código de país y la versión de la aplicación; tu IP nunca se envía allí.",
    "Country not checked.": "País sin consultar.",
    "Country statistics are disabled.": "Las estadísticas por país están desactivadas.",
    "Checking country...": "Consultando el país...",
    "Could not record country statistics: ": "No se pudieron guardar las estadísticas por país: ",
    "Connected from country: ": "País de conexión: ",
    "Could not save analytics preference: ": "No se pudo guardar la preferencia de estadísticas: ",
    "Flet interface connected to yt-dlp, Lamovie, Markdown, and torrent services.": "Interfaz de Flet conectada a los servicios de yt-dlp, Lamovie, Markdown y torrent.",
    "Select the download folder": "Selecciona la carpeta de descargas",
    "Could not save language preference: ": "No se pudo guardar el idioma: ",
    "Stop download": "Detener descarga",
}
_SPANISH_TO_ENGLISH = {
    spanish: english for english, spanish in _ENGLISH_TO_SPANISH.items()
}


class PresentationComponents:
    page: ft.Page
    main_container: ft.Container
    language: str

    def _t(self, text: str) -> str:
        translations = (
            _ENGLISH_TO_SPANISH
            if getattr(self, "language", "es") == "es"
            else _SPANISH_TO_ENGLISH
        )
        translated = translations.get(text)
        if translated is not None:
            return translated
        for source in sorted(translations, key=len, reverse=True):
            if source and text.startswith(source):
                return translations[source] + self._t(text[len(source):])
        return text

    def _translate_control(self, control):
        for attribute in ("value", "label", "hint_text", "tooltip", "title", "subtitle", "text"):
            value = getattr(control, attribute, None)
            if isinstance(value, str):
                setattr(control, attribute, self._t(value))
        for option in getattr(control, "options", []):
            text = getattr(option, "text", None)
            if isinstance(text, str):
                option.text = self._t(text)
        for attribute in ("controls", "actions", "destinations"):
            for child in getattr(control, attribute, []):
                self._translate_control(child)
        for attribute in ("content", "leading", "trailing", "title"):
            child = getattr(control, attribute, None)
            if isinstance(child, str):
                setattr(control, attribute, self._t(child))
            elif child is not None:
                self._translate_control(child)

    def _section_heading(self, title: str, subtitle: str, icon):
        return ft.Row(
            [
                ft.Container(
                    content=ft.Icon(icon, color=ft.Colors.INDIGO_600, size=28),
                    width=48,
                    height=48,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ft.Colors.SECONDARY_CONTAINER,
                    border_radius=12,
                ),
                ft.Column(
                    [
                        ft.Text(title, size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(subtitle, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _surface(self, content, padding: int = 24):
        return ft.Container(
            content=content,
            padding=padding,
            bgcolor=ft.Colors.TRANSPARENT,
            border_radius=16,
        )

    def _metric_card(self, label: str, value: int, icon, accent):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon, color=accent, size=28),
                        width=56,
                        height=56,
                        alignment=ft.Alignment.CENTER,
                        bgcolor=ft.Colors.with_opacity(0.1, accent),
                        border_radius=14,
                    ),
                    ft.Column(
                        [
                            ft.Text(label, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(str(value), size=28, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                ],
                spacing=16,
            ),
            width=220,
            padding=20,
            bgcolor=ft.Colors.TRANSPARENT,
            border_radius=16,
        )

    def _render_page(self, content):
        self._translate_control(content)
        self.main_container.content = content
        self.page.update()

    def _show_message(self, message: str, bgcolor=None):
        self.page.show_dialog(
            ft.SnackBar(
                content=ft.Text(self._t(message)),
                bgcolor=bgcolor,
                behavior=ft.SnackBarBehavior.FLOATING,
            )
        )

    def _dismiss_dialog(self):
        self.page.pop_dialog()

    def _status_badge(self, status: str):
        palette = {
            "active": (ft.Colors.TEAL_50, ft.Colors.TEAL_800),
            "archived": (ft.Colors.ORANGE_50, ft.Colors.ORANGE_800),
            "draft": (ft.Colors.BLUE_GREY_100, ft.Colors.BLUE_GREY_800),
        }
        background, foreground = palette.get(
            status.lower(),
            (ft.Colors.BLUE_GREY_100, ft.Colors.BLUE_GREY_800),
        )
        return ft.Container(
            content=ft.Text(
                status.title(),
                size=12,
                color=foreground,
                weight=ft.FontWeight.W_500,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            bgcolor=background,
            border_radius=20,
        )
