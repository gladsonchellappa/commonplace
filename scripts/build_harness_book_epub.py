#!/usr/bin/env python3
"""Build a timestamped EPUB 3 edition from the AI Harness Engineering book."""
from __future__ import annotations
import html
import re
import zipfile
from datetime import datetime
from pathlib import Path
import markdown
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SOURCE = DOCS / "11.02-0900-ai-harness-engineering-book.md"
OUT = DOCS / "downloads"
STAMP = datetime.now().astimezone().strftime("%m.%d-%H%M")
NAME = f"{STAMP}-ai-harness-engineering-book.epub"
CSS = """
body{font-family:serif;line-height:1.55;margin:5%;color:#222}
h1,h2,h3,h4{font-family:sans-serif;line-height:1.2}
h1{font-size:2em;margin-top:1.5em}h2{font-size:1.5em;margin-top:1.5em}
p{margin:.55em 0 1em}li{margin:.35em 0}
.titlepage{page-break-after:always;text-align:center;margin-top:28%}
.subtitle{font-style:italic;color:#555}
pre{white-space:pre-wrap;word-wrap:break-word;background:#f4f3ef;padding:.7em;border:1px solid #ddd}
code{font-family:monospace;font-size:.85em}
table{border-collapse:collapse;width:100%;font-size:.9em}
td,th{border:1px solid #aaa;padding:.4em;vertical-align:top}
a{color:#234a8b}
"""

def main():
    raw = SOURCE.read_text(encoding="utf-8")
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", raw, count=1, flags=re.S)
    rendered = markdown.markdown(body, extensions=["tables", "fenced_code", "toc"])
    soup = BeautifulSoup(rendered, "html.parser")
    for image in soup.find_all("img"):
        image["src"] = "../images/" + Path(image["src"]).name
    sections = []
    current_title = "Preface"
    current_nodes = []
    for node in list(soup.contents):
        if getattr(node, "name", None) == "h1":
            if current_nodes:
                sections.append((current_title, "".join(str(x) for x in current_nodes)))
            current_title = node.get_text(" ", strip=True)
            current_nodes = [node]
        else:
            current_nodes.append(node)
    if current_nodes:
        sections.append((current_title, "".join(str(x) for x in current_nodes)))
    sections.insert(0, ("Title", '<div class="titlepage"><h1>AI Harness Engineering</h1><p class="subtitle">Designing the environment in which autonomous intelligence operates</p><p>Gladson Chellappa · Commonplace · November 2026</p></div>'))

    OUT.mkdir(parents=True, exist_ok=True)
    uid = f"urn:uuid:commonplace-ai-harness-{STAMP}"
    manifest, spine, nav, chapter_files = [], [], [], []
    for i, (title, content) in enumerate(sections, 1):
        href = f"text/chapter{i:02d}.xhtml"
        doc = ('<?xml version="1.0" encoding="utf-8"?>'
               '<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" '
               'xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">'
               '<head><title>'+html.escape(title)+'</title><link rel="stylesheet" type="text/css" href="../styles/book.css"/></head>'
               '<body>'+content+'</body></html>')
        chapter_files.append(("OEBPS/"+href, doc))
        manifest.append(f'<item id="c{i}" href="{href}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{i}"/>')
        nav.append(f'<li><a href="{href}">{html.escape(title)}</a></li>')

    image_files = sorted((DOCS / "images").glob("*.svg"))
    image_manifest = "".join('<item id="img%d" href="images/%s" media-type="image/svg+xml"/>' % (i,p.name) for i,p in enumerate(image_files, 1))
    opf = ('<?xml version="1.0" encoding="utf-8"?>'
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="en">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           f'<dc:identifier id="uid">{uid}</dc:identifier><dc:title>AI Harness Engineering</dc:title>'
           '<dc:language>en</dc:language><dc:creator>Gladson Chellappa</dc:creator>'
           f'<meta property="dcterms:modified">{datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>'
           '</metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
           '<item id="css" href="styles/book.css" media-type="text/css"/>'
           + "".join(manifest) + image_manifest + '</manifest><spine>' + "".join(spine) + '</spine></package>')
    navdoc = ('<?xml version="1.0" encoding="utf-8"?>'
              '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en">'
              '<head><title>Contents</title></head><body><nav epub:type="toc" id="toc"><h1>Contents</h1><ol>'
              + "".join(nav) + '</ol></nav></body></html>')
    target = OUT / NAME
    tmp = OUT / (NAME + ".tmp")
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/nav.xhtml", navdoc)
        z.writestr("OEBPS/styles/book.css", CSS)
        for path, data in chapter_files:
            z.writestr(path, data)
        for p in image_files:
            z.write(p, "OEBPS/images/" + p.name)
    tmp.replace(target)

    source_text = SOURCE.read_text(encoding="utf-8")
    marker = "<!-- BOOK_EPUB -->"
    link = f'<p><strong>Kindle edition:</strong> <a href="./downloads/{NAME}">Download the EPUB</a> · {STAMP}</p>'
    if marker in source_text:
        source_text = re.sub(re.escape(marker)+r".*?<!-- /BOOK_EPUB -->", marker+link+"<!-- /BOOK_EPUB -->", source_text, flags=re.S)
    else:
        source_text += "\n\n"+marker+link+"<!-- /BOOK_EPUB -->\n"
    SOURCE.write_text(source_text, encoding="utf-8")
    print(f"Built {NAME} with {len(sections)} navigable sections")

if __name__ == "__main__":
    main()
