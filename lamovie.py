import argparse
import json
import re
import sys
import unittest
import urllib.parse
import urllib.request
from unittest.mock import patch


FAST_API = "https://lamovie.org/wp-api/v1"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

POST_TYPES = {
    "peliculas": "movies",
    "movies": "movies",
    "series": "tvshows",
    "tvshows": "tvshows",
    "animes": "animes",
    "novelas": "novels",
    "wwe": "wwe",
    "proximamente": "upcoming_movies",
    "colecciones": "collections",
}


def fetch_json(url, timeout=30):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Referer": "https://lamovie.org/",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def parse_lamovie_url(url):
    parsed = urllib.parse.urlparse(url)
    if "lamovie.org" not in (parsed.netloc or ""):
        return None, None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2:
        post_type = POST_TYPES.get(parts[0])
        if post_type:
            return parts[1], post_type
    return None, None


def resolve_lamovie(url):
    slug, post_type = parse_lamovie_url(url)
    if not slug:
        raise ValueError("URL de lamovie.org no válida o no soportada")

    single_url = FAST_API + "/single/" + post_type + "?" + urllib.parse.urlencode(
        {"slug": slug, "postType": post_type}
    )
    single = fetch_json(single_url)
    if single.get("error") or not single.get("data"):
        raise ValueError(f"No se encontró el contenido: {url}")

    data = single["data"]
    post_id = data["_id"]

    player_url = FAST_API + "/player?" + urllib.parse.urlencode(
        {"postId": post_id, "demo": 0}
    )
    player = fetch_json(player_url)
    player_data = player.get("data") or {}

    return {
        "id": post_id,
        "title": data.get("title"),
        "overview": data.get("overview"),
        "slug": slug,
        "post_type": post_type,
        "imdb_rating": data.get("imdb_rating"),
        "release_date": data.get("release_date"),
        "runtime": data.get("runtime"),
        "genres": data.get("genres"),
        "quality": data.get("quality"),
        "lang": data.get("lang"),
        "countries": data.get("countries"),
        "embeds": player_data.get("embeds", []),
        "downloads": player_data.get("downloads", []),
    }


class TestLamovie(unittest.TestCase):
    def test_parse_lamovie_url_movie(self):
        slug, post_type = parse_lamovie_url("https://lamovie.org/peliculas/don-q-2024/")
        self.assertEqual(slug, "don-q-2024")
        self.assertEqual(post_type, "movies")

    def test_parse_lamovie_url_series(self):
        slug, post_type = parse_lamovie_url("https://lamovie.org/series/una-serie-2024/")
        self.assertEqual(slug, "una-serie-2024")
        self.assertEqual(post_type, "tvshows")

    def test_parse_lamovie_url_other_domain(self):
        slug, post_type = parse_lamovie_url("https://example.com/peliculas/x/")
        self.assertIsNone(slug)
        self.assertIsNone(post_type)

    def _get_module_name(self):
        return "__main__" if __name__ == "__main__" else "lamovie"

    def test_resolve_lamovie(self):
        mod = self._get_module_name()
        with patch(f"{mod}.fetch_json") as mock_fetch:
            mock_fetch.side_effect = [
                {
                    "error": False,
                    "data": {
                        "_id": 44306,
                        "title": "Don Q (2024)",
                        "overview": "Sinopsis de prueba",
                        "imdb_rating": 6,
                    },
                },
                {
                    "error": False,
                    "data": {
                        "embeds": [
                            {"url": "https://voe.sx/e/abc", "lang": "Latino"}
                        ],
                        "downloads": [
                            {
                                "url": "magnet:?xt=urn:btih:abc",
                                "server": "Torrent",
                            }
                        ],
                    },
                },
            ]
            result = resolve_lamovie("https://lamovie.org/peliculas/don-q-2024/")
            self.assertEqual(result["id"], 44306)
            self.assertEqual(result["title"], "Don Q (2024)")
            self.assertEqual(len(result["embeds"]), 1)
            self.assertEqual(len(result["downloads"]), 1)
            calls = [c.args[0] for c in mock_fetch.call_args_list]
            self.assertIn("slug=don-q-2024", calls[0])
            self.assertIn("postId=44306", calls[1])

    def test_resolve_lamovie_not_found(self):
        mod = self._get_module_name()
        with patch(f"{mod}.fetch_json") as mock_fetch:
            mock_fetch.return_value = {"error": True, "message": "not found", "data": []}
            with self.assertRaises(ValueError):
                resolve_lamovie("https://lamovie.org/peliculas/inexistente-2024/")

    def test_resolve_lamovie_invalid_url(self):
        with self.assertRaises(ValueError):
            resolve_lamovie("https://example.com/peliculas/x/")


def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestLamovie)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(
        description="Resuelve páginas de lamovie.org a sus enlaces reales"
    )
    parser.add_argument("url", nargs="?", help="URL de lamovie.org")
    parser.add_argument("--test", action="store_true", help="Ejecutar pruebas unitarias")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    if not args.url:
        parser.print_help()
        sys.exit(1)

    result = resolve_lamovie(args.url)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
