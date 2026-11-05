import os
import sys
import yt_dlp


def descargar_video(url, formato="mp4", calidad="best", carpeta="downloads"):
    """
    Descarga un video de casi cualquier sitio web.

    Parámetros:
        url: URL del video
        formato: 'mp4' o 'mkv'
        calidad: 'best', '720', '1080', '480', 'worst'
        carpeta: directorio donde guardar el archivo
    """
    os.makedirs(carpeta, exist_ok=True)

    # Mapeo de calidades a formatos de yt-dlp
    formatos_calidad = {
        "best":  "bestvideo+bestaudio/best",
        "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "worst": "worstvideo+worstaudio/worst",
    }

    format_selector = formatos_calidad.get(calidad, formatos_calidad["best"])

    # Plantilla de nombre de archivo
    outtmpl = os.path.join(carpeta, "%(title)s.%(ext)s")

    ydl_opts = {
        "format": format_selector,
        "outtmpl": outtmpl,
        "merge_output_format": formato,        # Fuerza mp4 o mkv al combinar
        "noplaylist": True,                    # Descarga solo el video, no la lista
        "quiet": False,
        "no_warnings": False,
        "console_logger": None,
        "progress_hooks": [progreso_hook],
        # Si el sitio requiere cookies, descomenta la siguiente línea:
        # "cookiefile": "cookies.txt",
    }

    print(f"\n🔗 URL: {url}")
    print(f"📦 Formato: {formato.upper()}  |  🎬 Calidad: {calidad}")
    print("-" * 50)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            archivo = ydl.prepare_filename(info)
            # Cambiar la extensión al formato final
            base, _ = os.path.splitext(archivo)
            archivo_final = f"{base}.{formato}"
            print(f"\n✅ Descarga completa: {archivo_final}")
            return archivo_final
    except yt_dlp.utils.DownloadError as e:
        print(f"\n❌ Error al descargar: {e}")
        mensaje = str(e).lower()
        if any(indicador in mensaje for indicador in (
            "only works when logged-in",
            "requires authentication",
            "login required",
            "sign in",
        )):
            print(
                "\n🔐 Este sitio requiere iniciar sesión. Inicia sesión en el sitio "
                "desde tu navegador y vuelve a intentarlo. Si el video sigue "
                "requiriendo autenticación, configura yt-dlp para usar las cookies "
                "de ese navegador; el programa no solicitará ni guardará tu contraseña."
            )
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
    return None


def progreso_hook(d):
    """Muestra una barra de progreso sencilla."""
    if d["status"] == "downloading":
        porcentaje = d.get("_percent_str", "N/A").strip()
        velocidad = d.get("_speed_str", "N/A").strip()
        eta = d.get("_eta_str", "N/A").strip()
        print(f"\r⏳ Descargando: {porcentaje} | Velocidad: {velocidad} | ETA: {eta}", end="")
    elif d["status"] == "finished":
        print(f"\n⚙️  Procesando/convirtiendo archivo...")


def main():
    print("=" * 50)
    print("   DESCARGADOR DE VIDEOS (MP4 / MKV)")
    print("=" * 50)

    url = input("\n🔗 Introduce la URL del video: ").strip()
    if not url:
        print("❌ URL vacía. Saliendo.")
        sys.exit(1)

    formato = input("📦 Formato (mp4/mkv) [mp4]: ").strip().lower() or "mp4"
    if formato not in ("mp4", "mkv"):
        print("⚠️  Formato no válido, usando mp4.")
        formato = "mp4"

    calidad = input("🎬 Calidad (best/1080/720/480/worst) [best]: ").strip().lower() or "best"
    if calidad not in ("best", "1080", "720", "480", "worst"):
        print("⚠️  Calidad no válida, usando best.")
        calidad = "best"

    descargar_video(url, formato=formato, calidad=calidad)


if __name__ == "__main__":
    main()