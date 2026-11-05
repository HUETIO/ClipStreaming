import libtorrent as lt
import time

magnet = "magnet:?xt=urn:btih:2ee4089a31254b4bf7892945341ee7c2942cded9&dn=Don.Q.2023.1080P-Dual-Lat&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80%2Fannounce&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce&tr=udp%3A%2F%2Fopen.demonii.com%3A1337%2Fannounce&tr=udp%3A%2F%2Fexplodie.org%3A6969%2Fannounce&tr=wss%3A%2F%2Fwstracker.online&tr=http%3A%2F%2Fshare.camoe.cn%3A8080%2Fannounce&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce&tr=http%3A%2F%2Ft.nyaatracker.com%3A%3A80announce&tr=udp%3A%2F%2Fthetracker.org%3A80%2Fannounce&tr=udp%3A%2F%2Fbt.xxx-tracker.com%3A2710%2Fannounce&tr=udp%3A%2F%2Ftracker.vanitycore.co%3A6969%2Fannounce&tr=http%3A%2F%2Ftracker.tfile.me%3A80%2Fannounce&tr=udp%3A%2F%2Ftracker.tiny-vps.com%3A6969%2Fannounce&tr=http%3A%2F%2Fretracker.telecom.by%3A80%2Fannounce&tr=http%3A%2F%2Ftracker.electro-torrent.pl%3A80%2Fannounce&tr=udp%3A%2F%2Ftracker.justseed.it%3A1337%2Fannounce&tr=udp%3A%2F%2Ftracker.leechers-paradise.org%3A6969%2Fannounce&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969%2Fannounce&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce&tr=http%3A%2F%2Fretracker.mgts.by%3A80%2Fannounce&tr=udp%3A%2F%2Ftracker.cypherpunks.ru%3A6969%2Fannounce&tr=udp%3A%2F%2Ftracker.cyberia.is%3A6969%2Fannounce&tr=udp%3A%2F%2Fretracker.lanta-net.ru%3A2710%2Fannounce&tr=udp%3A%2F%2Ftracker.internetwarriors.net%3A1337%2Fannounce&tr=udp%3A%2F%2Ftracker.swateam.org.uk%3A2710%2Fannounce"

ses = lt.session()
ses.listen_on(6881, 6891)
params = {
    "save_path": "downloads/torrent",
    "url": magnet,
}
h = ses.add_torrent(params)
print("Añadido. Obteniendo metadata...")
for i in range(30):
    s = h.status()
    if s.has_metadata:
        break
    time.sleep(1)
    print(f"  esperando metadata... {s.state}")

print("has_metadata:", h.has_metadata)
if not h.has_metadata:
    print("ERROR: no se obtuvo metadata")
    raise SystemExit(1)

print("Nombre:", h.name())
print("Tamaño:", h.get_torrent_info().total_size() / (1024**3), "GB")
print("Peers:", h.status().num_peers, "Seeds:", h.status().num_seeds)

print("Descargando 20s de prueba...")
for i in range(20):
    s = h.status()
    print(f"  {s.progress*100:.1f}% | {s.download_rate/1024:.0f} KB/s | peers {s.num_peers}")
    time.sleep(1)

ses.remove_torrent(h)
print("OK - prueba finalizada")
