import os
import sys
import tempfile
import time
import unittest
from typing import Any, Callable
from unittest.mock import patch, MagicMock

try:
    import libtorrent as lt
except ImportError:
    lt = None


def is_available():
    return lt is not None


def download_torrent(
    magnet,
    output_dir="downloads/torrent",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    timeout: float | None = None,
    seed=False,
    metadata_timeout: float | None = 180,
) -> dict[str, Any]:
    if lt is None:
        raise RuntimeError("libtorrent no esta instalado. Ejecuta: pip install libtorrent")

    os.makedirs(output_dir, exist_ok=True)

    ses = lt.session()
    ses.listen_on(6881, 6891)
    # Nodos de arranque DHT para poder resolver peers aunque los trackers fallen.
    for _router, _port in (
        ("router.bittorrent.com", 6881),
        ("dht.transmissionbt.com", 6881),
        ("router.utorrent.com", 6881),
    ):
        try:
            ses.add_dht_router(_router, _port)
        except Exception:
            pass

    params = lt.parse_magnet_uri(magnet)
    params.save_path = output_dir
    # Los magnet suelen venir con el flag "paused"; si no se quita, libtorrent
    # nunca busca peers ni metadatos y la descarga parece no avanzar.
    params.flags &= ~lt.torrent_flags.paused
    params.flags |= lt.torrent_flags.auto_managed
    if seed:
        params.flags &= ~lt.torrent_flags.auto_managed
        params.flags |= lt.torrent_flags.seed_mode

    handle = ses.add_torrent(params)
    # Algunas versiones de libtorrent agregan el magnet en pausa aunque se
    # limpie el flag; reanudamos explícitamente para forzar la descarga.
    try:
        handle.resume()
    except Exception:
        pass
    start = time.monotonic()

    def report(event: dict[str, Any]) -> None:
        if progress_callback:
            progress_callback(event)

    def report_alerts() -> None:
        for alert in ses.pop_alerts():
            message = alert.message().strip()
            if message:
                report({"type": "log", "message": message})

    def make_progress_event(status, stage: str, total_size: int = 0) -> dict[str, Any]:
        return {
            "type": "progress",
            "stage": stage,
            "progress": status.progress if stage == "downloading" else None,
            "download_rate": status.download_rate,
            "upload_rate": status.upload_rate,
            "peers": status.num_peers,
            "seeds": status.num_seeds,
            "connections": status.num_connections,
            "downloaded": status.total_done,
            "total_size": total_size,
            "elapsed": time.monotonic() - start,
        }

    try:
        report(
            {
                "type": "log",
                "message": "Conectando con trackers y buscando peers (DHT/LSD).",
            }
        )
        metadata_started = time.monotonic()
        while True:
            report_alerts()
            status = handle.status()
            if status.has_metadata:
                break

            elapsed = time.monotonic() - start
            metadata_elapsed = time.monotonic() - metadata_started
            if metadata_timeout is not None and metadata_elapsed >= metadata_timeout:
                raise TimeoutError(
                    "No se recibieron metadatos. Comprueba que el magnet sea válido "
                    "y que tenga peers o trackers activos."
                )
            if timeout is not None and elapsed >= timeout:
                raise TimeoutError(
                    "Se agotó el tiempo máximo de descarga mientras se obtenían metadatos."
                )

            report(make_progress_event(status, "metadata"))
            time.sleep(1)

        name = handle.name()
        info = handle.torrent_file()
        total_size = info.total_size() if info else 0
        report({"type": "log", "message": f"Metadatos recibidos: {name} ({total_size} bytes)."})

        while True:
            report_alerts()
            status = handle.status()
            report(make_progress_event(status, "downloading", total_size))
            if status.is_seeding or status.progress >= 1.0:
                break

            elapsed = time.monotonic() - start
            if timeout is not None and elapsed >= timeout:
                raise TimeoutError(
                    f"Se agotó el tiempo máximo de descarga; progreso alcanzado: "
                    f"{status.progress * 100:.1f}%."
                )
            time.sleep(1)

        report_alerts()
        return {
            "name": name,
            "size": total_size,
            "path": os.path.join(output_dir, name),
            "completed": status.progress >= 1.0,
        }
    finally:
        ses.remove_torrent(handle)


class TestTorrentDownloader(unittest.TestCase):
    def test_is_available(self):
        self.assertTrue(is_available())

    @patch("torrent_downloader.lt")
    def test_download_torrent(self, mock_lt):
        mock_ses = MagicMock()
        mock_lt.session.return_value = mock_ses
        mock_lt.parse_magnet_uri.return_value = MagicMock()
        mock_handle = MagicMock()
        mock_ses.add_torrent.return_value = mock_handle

        mock_status = MagicMock()
        mock_status.has_metadata = True
        mock_status.progress = 1.0
        mock_status.is_seeding = True
        mock_status.download_rate = 1024
        mock_status.num_peers = 5
        mock_status.num_seeds = 10
        mock_handle.status.return_value = mock_status
        mock_handle.name.return_value = "test.mkv"
        mock_info = MagicMock()
        mock_info.total_size.return_value = 1024 * 1024
        mock_handle.torrent_file.return_value = mock_info

        calls = []

        def cb(event):
            calls.append(event)

        with tempfile.TemporaryDirectory() as output_dir:
            result = download_torrent(
                "magnet:?xt=urn:btih:abc123",
                output_dir=output_dir,
                progress_callback=cb,
            )

        self.assertEqual(result["name"], "test.mkv")
        self.assertTrue(result["completed"])
        self.assertTrue(calls)
        self.assertIn("progress", {event.get("type") for event in calls})
        mock_ses.add_torrent.assert_called_once()
        mock_ses.remove_torrent.assert_called_once()

    @patch("torrent_downloader.lt")
    def test_metadata_timeout_reports_progress_and_removes_torrent(self, mock_lt):
        mock_ses = MagicMock()
        mock_lt.session.return_value = mock_ses
        mock_lt.parse_magnet_uri.return_value = MagicMock()
        mock_handle = MagicMock()
        mock_ses.add_torrent.return_value = mock_handle
        status = MagicMock()
        status.has_metadata = False
        status.num_peers = 0
        status.num_seeds = 0
        status.num_connections = 0
        status.download_rate = 0
        status.upload_rate = 0
        status.total_done = 0
        mock_handle.status.return_value = status

        events = []
        with tempfile.TemporaryDirectory() as output_dir:
            with patch("torrent_downloader.time.sleep"):
                with patch(
                    "torrent_downloader.time.monotonic",
                    side_effect=[0, 0, 0, 0, 0, 1, 1],
                ):
                    with self.assertRaisesRegex(TimeoutError, "No se recibieron metadatos"):
                        download_torrent(
                            "magnet:?xt=urn:btih:abc123",
                            output_dir=output_dir,
                            progress_callback=events.append,
                            metadata_timeout=0.5,
                        )

        self.assertIn("metadata", [event.get("stage") for event in events])
        mock_ses.remove_torrent.assert_called_once_with(mock_handle)

    def test_download_torrent_no_libtorrent(self):
        with patch("torrent_downloader.lt", None):
            with self.assertRaises(RuntimeError):
                download_torrent("magnet:?xt=urn:btih:abc123")


def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestTorrentDownloader)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


def main():
    if not is_available():
        print("libtorrent no esta instalado. Ejecuta: pip install libtorrent")
        sys.exit(1)

    import argparse

    parser = argparse.ArgumentParser(description="Descarga torrents por magnet link")
    parser.add_argument("magnet", nargs="?", help="Magnet link")
    parser.add_argument("-o", "--output", default="downloads/torrent")
    args = parser.parse_args()

    if not args.magnet:
        parser.print_help()
        sys.exit(1)

    def cb(event):
        if event["type"] == "log":
            print(f"\n{event['message']}")
        elif event["stage"] == "metadata":
            print(
                f"\rBuscando metadatos | {event['peers']} peers | "
                f"{event['elapsed']:.0f} s   ",
                end="",
                flush=True,
            )
        else:
            print(
                f"\r{event['progress'] * 100:5.1f}% | "
                f"{event['download_rate'] / 1024:7.0f} KB/s | "
                f"peers {event['peers']} seeds {event['seeds']}   ",
                end="",
                flush=True,
            )

    result = download_torrent(args.magnet, args.output, progress_callback=cb)
    print(f"\nCompletado: {result['name']} ({result['size']/(1024**3):.2f} GB)")
    print(f"Guardado en: {result['path']}")


if __name__ == "__main__":
    main()
