#!/usr/bin/env python3
"""Build timestamped EPUB 3 editions of the Commonplace study guides."""
from __future__ import annotations
import html
import json
import os
import re
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = DOCS / "downloads"
STAMP = datetime.now().astimezone().strftime("%m.%d-%H%M")
CSS = """
body{font-family:serif;line-height:1.55;margin:5%;color:#222}
h1,h2,h3,h4{font-family: sans-serif;line-height:1.2}
h1{font-size:2em;margin-top:1.5em}h2{font-size:1.55em;margin-top:1.7em}
h3{font-size:1.2em;margin-top:1.4em}h4{font-size:1em;margin-top:1.2em}
p{margin:.55em 0 1em}li{margin:.35em 0}
.titlepage{page-break-after:always;text-align:center;margin-top:28%}
.subtitle{font-style:italic;color:#555}
.kicker{font: bold .75em sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#555}
.topic{margin:1.5em 0;padding-top:.6em;border-top:1px solid #bbb}
.level{margin:.8em 0}.level-label{font:bold .78em sans-serif;letter-spacing:.07em;text-transform:uppercase;color:#3457a4}
.callout,.worked-example,.engineering,.deep-section,.leadership-lens{margin:1em 0;padding:.7em 1em;background:#f4f3ef}
summary{font-weight:bold}a{color:#234a8b}
img{max-width:100%;height:auto}
table{border-collapse:collapse;width:100%;font-size:.9em}td,th{border:1px solid #aaa;padding:.4em;vertical-align:top}
"""

def xhtml(title, body):
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">'
            '<head><title>'+html.escape(title)+'</title><link rel="stylesheet" type="text/css" href="../styles/book.css"/></head>'
            '<body>'+body+'</body></html>')

def p(text):
    return '<p>'+html.escape(str(text or "")).replace("\n\n","</p><p>").replace("\n","<br/>")+'</p>' if text else ""

def build_pm(path):
    raw = path.read_text(encoding="utf-8")
    m = re.search(r'const chapters=(\[.*?\]);\s*const [A-Za-z_$][\w$]*\s*=', raw, re.S)
    if not m:
        raise RuntimeError("Could not locate the structured chapter data in the AI PM guide.")
    chapters = json.loads(m.group(1))
    soup = BeautifulSoup(raw, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else "AI Systems & Technical Leadership"
    intro = soup.select_one("header")
    intro_html = '<div class="titlepage"><h1>'+html.escape(title.split(" — ")[0])+'</h1><p class="subtitle">A Commonplace technical field guide</p></div>'
    if intro:
        dek = intro.select_one(".dek")
        if dek: intro_html += p(dek.get_text(" ",strip=True))
    sections = [("Introduction", intro_html)]
    for ch in chapters:
        body = '<h1>'+html.escape(ch["title"])+'</h1>'+p(ch.get("intro"))+p(ch.get("studyIntro"))
        if ch.get("studyExample"):
            body += '<h2>End-to-end running example</h2>'+p(ch["studyExample"])
        for i,t in enumerate(ch.get("topics",[]),1):
            body += '<section class="topic"><h2>'+html.escape(t["title"])+'</h2><p class="level-label">Level 1 · Definition</p>'+p(t.get("def"))+p(t.get("definitionContext"))+'<p class="level-label">Level 2 · Explanation and mental model</p>'+p(t.get("meaning"))
            body += '<h3>Level 3 · Concepts, mechanics and practical use</h3><ul>'
            for concept in t.get("concepts",[]):
                body += '<li><strong>'+html.escape(str(concept[0]))+'</strong> — '+html.escape(str(concept[1]))+'</li>'
            body += '</ul><h3>Level 4 · Engineering deep dive</h3>'
            for label,key in [("Under the hood", "engineering"),("Implementation walkthrough","implementation"),("Failure modes and diagnostics","failureModes"),("Operational signals and measurements","signals"),("Design trade-offs","tradeoffs")]:
                body += '<h4>'+label+'</h4>'+p(t.get(key))
            qs=t.get("studyQuestions",[])
            if qs: body += '<h4>Study and discussion questions</h4><ol>'+''.join('<li>'+html.escape(str(q))+'</li>' for q in qs)+'</ol>'
            body += '</section>'
        sections.append((ch["title"],body))
    refs = soup.select_one(".references")
    if refs:
        sections.append(("References",str(refs)))
    return title, sections

def clean_static_section(section):
    clone = BeautifulSoup(str(section), "html.parser")
    for node in clone.select("script,style,nav,button,summary"):
        node.decompose()
    for d in clone.select("details"):
        d.unwrap()
    for node in clone.select(".topic-kicker,.side-label,.eyebrow"):
        node.decompose()
    for a in clone.select("a"):
        a["href"] = a.get("href","#")
    return str(clone)

def build_harness(path):
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    title = soup.title.get_text(" ",strip=True) if soup.title else "AI Harness Engineering"
    main = soup.find("main")
    intro = '<div class="titlepage"><h1>AI Harness Engineering</h1><p class="subtitle">Architecting the Runtime, Context, Control and Infrastructure for Autonomous Intelligence</p></div>'
    sections=[("Introduction",intro)]
    if main:
        for section in main.select("section.chapter"):
            h = section.find(["h1","h2"])
            name = h.get_text(" ",strip=True) if h else "Chapter"
            sections.append((name,clean_static_section(section)))
    return title,sections

def make_epub(title, sections, filename, identifier):
    OUT.mkdir(parents=True,exist_ok=True)
    tmp=OUT/(filename+".tmp")
    book_title=title.split(" — ")[0]
    uid="urn:uuid:"+identifier
    manifest=[]; spine=[]; nav=[]
    chapters=[]
    for i,(name,body) in enumerate(sections,1):
        href=f"text/chapter{i:02d}.xhtml"
        chapters.append((href,name,xhtml(name,body)))
        manifest.append(f'<item id="c{i}" href="{href}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{i}"/>')
        nav.append(f'<li><a href="{href}">{html.escape(name)}</a></li>')
    opf=f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="en">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="uid">{uid}</dc:identifier><dc:title>{html.escape(book_title)}</dc:title><dc:language>en</dc:language><dc:creator>Commonplace</dc:creator><meta property="dcterms:modified">{datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%SZ")}</meta><meta property="belongs-to-collection">Commonplace Study Guides</meta></metadata>
<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="css" href="styles/book.css" media-type="text/css"/>{"".join(manifest)}</manifest>
<spine>{"".join(spine)}</spine></package>'''
    navdoc='<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en"><head><title>Contents</title></head><body><nav epub:type="toc" id="toc"><h1>Contents</h1><ol>'+''.join(nav)+'</ol></nav></body></html>'
    with zipfile.ZipFile(tmp,"w") as z:
        z.writestr("mimetype","application/epub+zip",compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",'<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf",opf)
        z.writestr("OEBPS/nav.xhtml",navdoc)
        z.writestr("OEBPS/styles/book.css",CSS)
        for href,name,content in chapters:
            z.writestr("OEBPS/"+href,content)
    tmp.replace(OUT/filename)

def add_download_link(page, label, href):
    s=page.read_text(encoding="utf-8")
    marker='<!-- EPUB_DOWNLOAD -->'
    block=f'<p class="epub-download" style="margin:18px 0;padding:12px 14px;border:1px solid #dedbd2;border-radius:8px;background:#fffdf9"><strong>Read on Kindle:</strong> <a href="{href}">Download the latest EPUB edition</a> <span style="color:#77746b;font-size:12px">({STAMP})</span></p>'
    if marker in s:
        s=re.sub(re.escape(marker)+r'.*?<!-- /EPUB_DOWNLOAD -->',marker+block+'<!-- /EPUB_DOWNLOAD -->',s,flags=re.S)
    else:
        s=s.replace('</header>','</header>\n'+marker+block+'<!-- /EPUB_DOWNLOAD -->',1)
    page.write_text(s,encoding="utf-8")

def main():
    pm_path=DOCS/"10.30-1700-ai-pm-knowledge.html"
    ha_path=DOCS/"10.31-1330-ai-harness-engineering.html"
    pm_title,pm_sections=build_pm(pm_path)
    ha_title,ha_sections=build_harness(ha_path)
    pm_name=f"{STAMP}-ai-systems-technical-leadership.epub"
    ha_name=f"{STAMP}-ai-harness-engineering.epub"
    make_epub(pm_title,pm_sections,pm_name,"ai-pm-"+STAMP)
    make_epub(ha_title,ha_sections,ha_name,"ai-harness-"+STAMP)
    add_download_link(pm_path,"AI Systems & Technical Leadership",f"./downloads/{pm_name}")
    add_download_link(ha_path,"AI Harness Engineering",f"./downloads/{ha_name}")
    index=DOCS/"index.html"
    content=index.read_text(encoding="utf-8")
    linkblock=f'<p class="epub-link"><a href="./downloads/{pm_name}">EPUB</a> · <a href="./downloads/{ha_name}">EPUB</a> <span>Latest Kindle editions · {STAMP}</span></p>'
    if "class=\"epub-link\"" in content:
        content=re.sub(r'<p class="epub-link">.*?</p>',linkblock,content,flags=re.S)
    else:
        content=content.replace('</section>\n    </main>',linkblock+'\n      </section>\n    </main>',1)
    index.write_text(content,encoding="utf-8")
    print(f"Generated {pm_name} ({len(pm_sections)} sections) and {ha_name} ({len(ha_sections)} sections)")

if __name__=="__main__":
    main()
