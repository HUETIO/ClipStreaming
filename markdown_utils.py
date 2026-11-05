import argparse
import html
import json
import os
import re
import sys
import unittest
import urllib.request
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import urlparse


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_HEADING_PREFIX = {
    "h1": "#",
    "h2": "##",
    "h3": "###",
    "h4": "####",
    "h5": "#####",
    "h6": "######",
}
_SKIP_TAGS = ("script", "style", "noscript", "svg", "head", "template")


def fetch_html(url, timeout=30):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _clean_text(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def _meta_content(html_text, attribute, value):
    tag_match = re.search(
        rf'<meta\b[^>]*\b{attribute}=["\']{re.escape(value)}["\'][^>]*>',
        html_text,
        re.IGNORECASE,
    )
    if not tag_match:
        return None
    content_match = re.search(
        r'\bcontent=["\'](.*?)["\']', tag_match.group(0), re.IGNORECASE | re.DOTALL
    )
    return html.unescape(content_match.group(1)) if content_match else None


def extract_metadata(html_text, url=None):
    metadata = {
        "title": _clean_text(_meta_content(html_text, "property", "og:title")),
        "description": _clean_text(_meta_content(html_text, "property", "og:description")),
        "image": _meta_content(html_text, "property", "og:image"),
        "site_name": _clean_text(_meta_content(html_text, "property", "og:site_name")),
        "canonical": None,
        "breadcrumbs": [],
        "url": url,
    }

    if not metadata["title"]:
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL
        )
        if title_match:
            metadata["title"] = _clean_text(title_match.group(1))
    if not metadata["description"]:
        metadata["description"] = _clean_text(_meta_content(html_text, "name", "description"))

    canonical_match = re.search(
        r'<link\b[^>]*\brel=["\']canonical["\'][^>]*>', html_text, re.IGNORECASE
    )
    if canonical_match:
        href_match = re.search(
            r'\bhref=["\'](.*?)["\']', canonical_match.group(0), re.IGNORECASE | re.DOTALL
        )
        if href_match:
            metadata["canonical"] = html.unescape(href_match.group(1))

    for script_match in re.finditer(
        r'<script\b[^>]*\btype=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    ):
        try:
            data = json.loads(html.unescape(script_match.group(1)))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            nodes = data.get("@graph", [])
        elif isinstance(data, list):
            nodes = data
        else:
            nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if not metadata["title"] and node.get("name"):
                metadata["title"] = _clean_text(str(node["name"]))
            if not metadata["description"] and node.get("description"):
                metadata["description"] = _clean_text(str(node["description"]))
            if node.get("@type") == "BreadcrumbList":
                for item in node.get("itemListElement", []):
                    if isinstance(item, dict) and item.get("name"):
                        metadata["breadcrumbs"].append(
                            {
                                "name": _clean_text(str(item["name"])),
                                "url": item.get("item"),
                            }
                        )

    return metadata


class _MarkdownConverter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts = []
        self._skip_depth = 0
        self._pre_depth = 0
        self._list_stack = []
        self._link = None

    def _emit(self, text):
        if self._link is not None:
            self._link[1].append(text)
        else:
            self._parts.append(text)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        if tag in _HEADING_PREFIX:
            self._emit("\n\n" + _HEADING_PREFIX[tag] + " ")
        elif tag == "p":
            self._emit("\n\n")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "code":
            self._emit("`")
        elif tag == "pre":
            self._pre_depth += 1
            self._emit("\n\n```\n")
        elif tag == "br":
            self._emit("\n")
        elif tag == "hr":
            self._emit("\n\n---\n\n")
        elif tag == "blockquote":
            self._emit("\n\n> ")
        elif tag == "ul":
            self._list_stack.append(["ul", 0])
            self._emit("\n")
        elif tag == "ol":
            self._list_stack.append(["ol", 0])
            self._emit("\n")
        elif tag == "li":
            if self._list_stack:
                kind, count = self._list_stack[-1]
                count += 1
                self._list_stack[-1][1] = count
                if kind == "ol":
                    self._emit(f"\n{count}. ")
                else:
                    self._emit("\n- ")
            else:
                self._emit("\n- ")
        elif tag == "a":
            attrs_dict = {k.lower(): v for k, v in attrs}
            self._link = (attrs_dict.get("href", ""), [])
        elif tag == "img":
            attrs_dict = {k.lower(): v for k, v in attrs}
            self._emit(f"![{attrs_dict.get('alt', '')}]({attrs_dict.get('src', '')})")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in _HEADING_PREFIX or tag == "p" or tag == "blockquote":
            self._emit("\n\n")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "code":
            self._emit("`")
        elif tag == "pre":
            self._pre_depth = max(0, self._pre_depth - 1)
            self._emit("\n```\n\n")
        elif tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self._emit("\n")
        elif tag == "a" and self._link is not None:
            href, buffer = self._link
            text = "".join(buffer).strip()
            self._link = None
            if href and text:
                self._parts.append(f"[{text}]({href})")
            else:
                self._parts.append(text)

    def handle_data(self, data):
        if self._skip_depth:
            return
        if not self._pre_depth:
            data = re.sub(r"[ \t\r\n]+", " ", data)
        if self._link is not None:
            self._link[1].append(data)
        else:
            self._parts.append(data)

    def get_markdown(self):
        text = "".join(self._parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_markdown(html_text):
    body_match = re.search(r"<body[^>]*>(.*)</body>", html_text, re.IGNORECASE | re.DOTALL)
    content = body_match.group(1) if body_match else html_text
    converter = _MarkdownConverter()
    converter.feed(content)
    converter.close()
    return converter.get_markdown()


def slug_from_url(url):
    path = urlparse(url).path.strip("/")
    slug = path.rsplit("/", 1)[-1] if path else "pagina"
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", slug).strip("-")
    return slug or "pagina"


def generate_markdown(url, output_path=None):
    html_text = fetch_html(url)
    metadata = extract_metadata(html_text, url)
    content = html_to_markdown(html_text)

    title = metadata["title"] or url
    if metadata["site_name"] and title.endswith(" | " + metadata["site_name"]):
        title = title[: -len(" | " + metadata["site_name"])].strip()

    lines = [f"# {title}", ""]

    if metadata["description"]:
        lines.extend([metadata["description"], ""])

    lines.extend(["## Información", ""])
    lines.append(f"- **URL:** <{url}>")
    if metadata["canonical"] and metadata["canonical"] != url:
        lines.append(f"- **URL canónica:** <{metadata['canonical']}>")
    if metadata["site_name"]:
        lines.append(f"- **Sitio:** {metadata['site_name']}")
    if metadata["image"]:
        lines.append(f"- **Imagen:** {metadata['image']}")
    lines.append("")

    if metadata["breadcrumbs"]:
        lines.extend(["## Ruta de navegación", ""])
        for crumb in metadata["breadcrumbs"]:
            if crumb["url"]:
                lines.append(f"- [{crumb['name']}]({crumb['url']})")
            else:
                lines.append(f"- {crumb['name']}")
        lines.append("")

    lines.extend(["## Contenido de la página", ""])
    if content:
        lines.append(content)
    else:
        lines.append(
            "*(El contenido de esta página se renderiza dinámicamente en el navegador.)*"
        )
    lines.append("")

    if "lamovie.org" in (url or ""):
        try:
            import lamovie

            resolved = lamovie.resolve_lamovie(url)
            if resolved["embeds"]:
                lines.extend(["## Enlaces de reproducción", ""])
                lines.append("| Servidor | Idioma | Calidad | Enlace |")
                lines.append("| --- | --- | --- | --- |")
                for embed in resolved["embeds"]:
                    lines.append(
                        "| {} | {} | {} | {} |".format(
                            embed.get("server") or "-",
                            embed.get("lang") or "-",
                            embed.get("quality") or "-",
                            embed.get("url") or "-",
                        )
                    )
                lines.append("")
            if resolved["downloads"]:
                lines.extend(["## Descargas", ""])
                lines.append("| Servidor | Idioma | Calidad | Enlace |")
                lines.append("| --- | --- | --- | --- |")
                for download in resolved["downloads"]:
                    lines.append(
                        "| {} | {} | {} | {} |".format(
                            download.get("server") or "-",
                            download.get("lang") or "-",
                            download.get("quality") or "-",
                            download.get("url") or "-",
                        )
                    )
                lines.append("")
        except Exception:
            pass

    markdown_text = "\n".join(lines)

    if output_path:
        directory = os.path.dirname(output_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

    return markdown_text


class TestMarkdownUtils(unittest.TestCase):
    SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head>
<title>Título de prueba | Mi Sitio</title>
<meta property="og:title" content="Título OG">
<meta property="og:description" content="Descripción de prueba">
<meta property="og:image" content="https://example.com/img.jpg">
<meta property="og:site_name" content="Mi Sitio">
<link rel="canonical" href="https://example.com/canonical">
<script type="application/ld+json">{"@graph":[{"@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Inicio","item":"https://example.com"},{"@type":"ListItem","position":2,"name":"Prueba"}]}]}</script>
</head>
<body>
<h1>Encabezado</h1>
<p>Texto con <strong>negrita</strong> y <em>cursiva</em> y <a href="https://example.com/enlace">enlace</a>.</p>
<ul><li>Uno</li><li>Dos</li></ul>
<ol><li>Primero</li><li>Segundo</li></ol>
</body>
</html>"""

    def test_extract_metadata(self):
        meta = extract_metadata(self.SAMPLE_HTML, "https://example.com/pagina")
        self.assertEqual(meta["title"], "Título OG")
        self.assertEqual(meta["description"], "Descripción de prueba")
        self.assertEqual(meta["image"], "https://example.com/img.jpg")
        self.assertEqual(meta["site_name"], "Mi Sitio")
        self.assertEqual(meta["canonical"], "https://example.com/canonical")
        self.assertEqual(len(meta["breadcrumbs"]), 2)
        self.assertEqual(meta["breadcrumbs"][0]["name"], "Inicio")
        self.assertEqual(meta["breadcrumbs"][1]["name"], "Prueba")

    def test_extract_metadata_title_fallback(self):
        meta = extract_metadata("<html><head><title>Solo título</title></head></html>")
        self.assertEqual(meta["title"], "Solo título")

    def test_html_to_markdown(self):
        md = html_to_markdown(self.SAMPLE_HTML)
        self.assertIn("# Encabezado", md)
        self.assertIn("**negrita**", md)
        self.assertIn("*cursiva*", md)
        self.assertIn("[enlace](https://example.com/enlace)", md)
        self.assertIn("- Uno", md)
        self.assertIn("1. Primero", md)

    def test_html_to_markdown_skips_scripts(self):
        md = html_to_markdown("<body><script>var x = 1;</script><p>Visible</p></body>")
        self.assertNotIn("var x", md)
        self.assertIn("Visible", md)

    def test_html_to_markdown_pre(self):
        md = html_to_markdown("<pre>code\nblock</pre>")
        self.assertIn("```", md)

    def test_slug_from_url(self):
        self.assertEqual(
            slug_from_url("https://lamovie.org/peliculas/don-q-2024/"), "don-q-2024"
        )

    def _get_module_name(self):
        return "__main__" if __name__ == "__main__" else "markdown_utils"

    def test_generate_markdown_writes_file(self):
        import tempfile

        mod = self._get_module_name()
        with patch(f"{mod}.fetch_html") as mock_fetch:
            mock_fetch.return_value = self.SAMPLE_HTML
            with tempfile.TemporaryDirectory() as tmp_dir:
                path = os.path.join(tmp_dir, "prueba.md")
                markdown_text = generate_markdown("https://example.com/pagina", path)
                self.assertTrue(os.path.exists(path))
                with open(path, encoding="utf-8") as f:
                    saved = f.read()
                self.assertIn("# Título OG", saved)
                self.assertIn("- **URL:** <https://example.com/pagina>", saved)
                self.assertIn("[Inicio](https://example.com)", saved)
                self.assertEqual(markdown_text, saved)


def run_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestMarkdownUtils)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description="Genera un archivo Markdown desde una URL")
    parser.add_argument("url", nargs="?", help="URL de la página")
    parser.add_argument("-o", "--output", help="Ruta de salida del archivo .md")
    parser.add_argument("--test", action="store_true", help="Ejecutar pruebas unitarias")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    if not args.url:
        parser.print_help()
        sys.exit(1)

    output = args.output
    if not output:
        output = os.path.join("downloads", "markdown", slug_from_url(args.url) + ".md")

    generate_markdown(args.url, output)
    print(f"Markdown guardado en: {output}")


if __name__ == "__main__":
    main()
