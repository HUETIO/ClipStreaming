"""
Descargador de torrents en Python (libtorrent): acepta .torrent o enlace magnet

Instalación (Windows, dentro de tu entorno virtual):
    pip install libtorrent

Uso:
    python descargar_torrent.py                          -> pide un magnet (o elegir un .torrent) y la carpeta
    python descargar_torrent.py archivo.torrent          -> pregunta solo la carpeta
    python descargar_torrent.py "magnet:?xt=urn:btih:..." -o D:\\Descargas

Úsalo solo con contenido que tengas derecho a descargar y compartir.
"""
import argparse
import os
import sys
import threading
import time
from typing import Any, Callable


TIMEOUT_METADATOS = 300   # segundos que esperas a que aparezcan peers/metadatos (solo magnets)

TRACKERS_EXTRA = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://explodie.org:6969/announce",
]


try:
    import libtorrent as lt
except ImportError:
    lt = None


def is_available():
    return lt is not None


def es_magnet(texto: str) -> bool:
    return bool(texto) and texto.strip().lower().startswith("magnet:?")


def crear_root_oculto():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def elegir_fuente_gui(root):
    """Pide un magnet; si se deja vacío, abre el selector de .torrent."""
    from tkinter import filedialog, simpledialog

    texto = simpledialog.askstring(
        "Torrent",
        "Pega el enlace magnet\n(deja vacío para elegir un archivo .torrent):",
        parent=root,
    )
    if texto and texto.strip():
        return texto.strip()
    return filedialog.askopenfilename(
        title="Selecciona el archivo .torrent",
        filetypes=[("Torrent", "*.torrent"), ("Todos", "*.*")],
    )


def elegir_carpeta_gui(root):
    from tkinter import filedialog

    return filedialog.askdirectory(title="Carpeta donde guardar la descarga")


def fmt_tam(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def mostrar_info(info, destino):
    print(f"\nTorrent : {info.name()}")
    print(f"Tamaño  : {fmt_tam(info.total_size())}")
    fs = info.files()
    print(f"Archivos: {fs.num_files()}")
    for i in range(min(fs.num_files(), 15)):
        print(f"  - {fs.file_path(i)}  ({fmt_tam(fs.file_size(i))})")
    if fs.num_files() > 15:
        print(f"  ... y {fs.num_files() - 15} más")
    print(f"Destino : {destino}\n")


def descargar(
    fuente: str,
    destino: str,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    metadata_timeout: float = TIMEOUT_METADATOS,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Descarga un magnet o archivo torrent y emite eventos de progreso."""
    if lt is None:
        raise RuntimeError("Falta libtorrent. Instálalo con: pip install libtorrent")

    fuente = fuente.strip().strip('"')
    magnet = es_magnet(fuente)
    if not magnet and not os.path.isfile(fuente):
        raise ValueError("No es un magnet válido ni un archivo .torrent existente.")
    os.makedirs(destino, exist_ok=True)

    def report(event: dict[str, Any]) -> None:
        if progress_callback:
            progress_callback(event)

    ses = lt.session({
        "listen_interfaces": "0.0.0.0:6881,[::]:6881",
        "enable_dht": True,
        "enable_lsd": True,
        "enable_upnp": False,      # evita el spam de "no router found"
        "enable_natpmp": False,
        "announce_to_all_trackers": True,
        "announce_to_all_tiers": True,
        "dht_bootstrap_nodes": (
            "router.bittorrent.com:6881,"
            "router.utorrent.com:6881,"
            "dht.transmissionbt.com:6881"
        ),
    })

    # --- Añadir el torrent (magnet o .torrent) ---
    if magnet:
        params = lt.parse_magnet_uri(fuente)
        params.trackers = list(params.trackers) + [
            tracker for tracker in TRACKERS_EXTRA if tracker not in params.trackers
        ]
        params.flags &= ~lt.torrent_flags.paused
        params.flags |= lt.torrent_flags.auto_managed
    else:
        params = lt.add_torrent_params()
        params.ti = lt.torrent_info(fuente)
    params.save_path = destino
    handle = ses.add_torrent(params)
    if magnet:
        handle.resume()

    start = time.monotonic()

    try:
        # --- Fase 1: metadatos (solo aplica a magnets) ---
        if magnet:
            metadata_started = time.monotonic()
            while not handle.status().has_metadata:
                if cancel_event and cancel_event.is_set():
                    raise InterruptedError("Descarga detenida por el usuario.")
                report_alerts(ses, report)
                s = handle.status()
                elapsed = time.monotonic() - start
                metadata_elapsed = time.monotonic() - metadata_started
                if s.errc.value() != 0:
                    raise RuntimeError(f"Error del torrent: {s.errc.message()}")
                if metadata_elapsed >= metadata_timeout:
                    raise TimeoutError(
                        "No se obtuvieron metadatos. Comprueba que el magnet tenga "
                        "peers activos y que tu red permita conexiones torrent."
                    )
                report(
                    {
                        "type": "progress",
                        "stage": "metadata",
                        "progress": None,
                        "download_rate": s.download_rate,
                        "upload_rate": s.upload_rate,
                        "peers": s.num_peers,
                        "seeds": s.num_seeds,
                        "connections": s.num_connections,
                        "downloaded": s.total_done,
                        "total_size": 0,
                        "elapsed": elapsed,
                    }
                )
                time.sleep(1)

        info = handle.torrent_file()
        name = info.name()
        total_size = info.total_size()
        report(
            {
                "type": "log",
                "message": f"Metadatos recibidos: {name} ({fmt_tam(total_size)}).",
            }
        )

        # --- Fase 2: descarga ---
        while True:
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Descarga detenida por el usuario.")
            report_alerts(ses, report)
            s = handle.status()
            if s.errc.value() != 0:
                raise RuntimeError(f"Error del torrent: {s.errc.message()}")
            report(
                {
                    "type": "progress",
                    "stage": "downloading",
                    "progress": s.progress,
                    "download_rate": s.download_rate,
                    "upload_rate": s.upload_rate,
                    "peers": s.num_peers,
                    "seeds": s.num_seeds,
                    "connections": s.num_connections,
                    "downloaded": s.total_done,
                    "total_size": total_size,
                    "elapsed": time.monotonic() - start,
                }
            )

            if s.is_seeding or s.is_finished:
                return {
                    "name": name,
                    "size": total_size,
                    "path": os.path.join(destino, name),
                    "completed": s.progress >= 1.0,
                }
            time.sleep(1)
    finally:
        ses.remove_torrent(handle)


def report_alerts(ses, report: Callable[[dict[str, Any]], None]) -> None:
    for alert in ses.pop_alerts():
        message = alert.message().strip()
        if message:
            report({"type": "log", "message": message})


def main():
    if not is_available():
        sys.exit("Falta libtorrent. Instálalo con: pip install libtorrent")

    parser = argparse.ArgumentParser(description="Abrir y descargar .torrent o enlaces magnet")
    parser.add_argument("torrent", nargs="?", help="ruta al .torrent o enlace magnet (entre comillas)")
    parser.add_argument("-o", "--salida", help="carpeta de destino")
    args = parser.parse_args()

    root = None
    fuente = args.torrent
    if not fuente:
        root = crear_root_oculto()
        fuente = elegir_fuente_gui(root)

    if not fuente:
        sys.exit("No se indicó ningún magnet ni archivo .torrent.")
    if not es_magnet(fuente) and not os.path.isfile(fuente.strip().strip('"')):
        sys.exit("No es un magnet válido ni un archivo .torrent existente.")

    destino = args.salida
    if not destino:
        if root is None:
            root = crear_root_oculto()
        destino = elegir_carpeta_gui(root)
    if not destino:
        sys.exit("No se seleccionó carpeta de destino.")
    os.makedirs(destino, exist_ok=True)

    def mostrar_progreso(event):
        if event["type"] == "log":
            print(f"\n{event['message']}")
        elif event["stage"] == "metadata":
            print(
                f"\rBuscando metadatos... {event['elapsed']:.0f}s | "
                f"Pares: {event['peers']}   ",
                end="",
                flush=True,
            )
        else:
            print(
                f"\r{event['progress'] * 100:5.1f}% | "
                f"↓ {fmt_tam(event['download_rate'])}/s | "
                f"↑ {fmt_tam(event['upload_rate'])}/s | "
                f"Pares: {event['peers']} (seeds: {event['seeds']})   ",
                end="",
                flush=True,
            )

    try:
        resultado = descargar(fuente, destino, progress_callback=mostrar_progreso)
    except KeyboardInterrupt:
        print("\nDescarga pausada por el usuario.")
        return
    print(f"\n\n¡Descarga completada! Archivo: {resultado['path']}")


if __name__ == "__main__":
    main()