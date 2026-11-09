#!/usr/bin/env python3
"""Prova totes les pàgines de docs/ en mòbil i en ordinador (com a espiralosona.com).

Ús:  python3 tools/proves.py [--captures CARPETA] [--nomes adreça,adreça]

- Serveix docs/ a http://localhost:8765<arrel>/ (l'arrel és la de data/site.json: /lespiral/ en proves) i l'obre amb
  Playwright, bloquejant tot el que no sigui localhost (lletres de Google, mapes, YouTube).
- Per a cada pàgina i amplada: errors de JavaScript, scroll lateral, imatges que no carreguen i enllaços interns que
  no porten enlloc.
- Amb --captures, desa una captura de pàgina sencera de cada pàgina i amplada.
"""
import asyncio, functools, json, sys, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PORT = 8765
SITE = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))
BASE = urlparse(SITE["publish"]["url"]).path or "/"
SIZES = [("ordinador", 1440, 900, False), ("mobil", 390, 844, True)]


class Handler(SimpleHTTPRequestHandler):
    """Serveix docs/ sota l'arrel (/lespiral/...) i la 404.html quan no hi ha res, com GitHub Pages."""
    def translate_path(self, path):
        p = unquote(urlparse(path).path)
        if p.startswith(BASE):
            p = "/" + p[len(BASE):]
        return str(DOCS / p.lstrip("/"))

    def send_error(self, code, message=None, explain=None):
        if code == 404 and (DOCS / "404.html").exists():
            body = (DOCS / "404.html").read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().send_error(code, message, explain)

    def log_message(self, *a):
        pass


def serve():
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


def pages(only=None):
    out = []
    for f in sorted(DOCS.rglob("index.html")):
        rel = f.parent.relative_to(DOCS).as_posix()
        if rel.startswith("wp-content") or rel.startswith("feed") or rel.endswith("/feed"):
            continue
        txt = f.read_text(encoding="utf-8")
        if 'http-equiv="refresh"' in txt:
            continue
        path = "" if rel == "." else rel + "/"
        if only is None or path.strip("/") in only:
            out.append(path)
    return out


def exists(path):
    p = unquote(path)
    if p.startswith(BASE):
        p = p[len(BASE):]
    f = DOCS / p.lstrip("/")
    return f.is_file() or (f / "index.html").is_file()


async def main():
    from playwright.async_api import async_playwright
    shots = Path(sys.argv[sys.argv.index("--captures") + 1]) if "--captures" in sys.argv else None
    only = set(sys.argv[sys.argv.index("--nomes") + 1].split(",")) if "--nomes" in sys.argv else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=serve, daemon=True).start()
    problems, bad_links = [], set()
    todo = pages(only)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, w, h, mobile in SIZES:
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile)
            await ctx.route("**/*", lambda r: r.continue_() if urlparse(r.request.url).hostname in ("localhost", "127.0.0.1") else r.abort())
            page = await ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            for path in todo:
                errs.clear()
                await page.goto(f"http://localhost:{PORT}{BASE}{path}")
                await page.evaluate("document.querySelectorAll('.reveal').forEach(e=>e.classList.add('is-in'));"
                                    "document.querySelectorAll('img[loading=lazy]').forEach(i=>i.loading='eager')")
                await page.wait_for_load_state("networkidle")
                info = await page.evaluate("""() => {
                  const de = document.documentElement;
                  const links = [...document.querySelectorAll('a[href]')].map(a => a.href).filter(h => h.startsWith(location.origin));
                  const broken = [...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src'));
                  return {sw: de.scrollWidth, cw: de.clientWidth, links, broken};
                }""")
                for l in info["links"]:
                    u = urlparse(l)
                    if not exists(u.path):
                        bad_links.add(f"/{path} → {unquote(u.path)}")
                if info["sw"] > info["cw"] + 1:
                    problems.append(f"{name} /{path}: scroll lateral ({info['sw']} > {info['cw']})")
                for e in errs:
                    problems.append(f"{name} /{path}: error de JavaScript: {e}")
                for i in info["broken"]:
                    problems.append(f"{name} /{path}: no carrega la imatge {i}")
                if shots:
                    fn = shots / f"{(path.strip('/').replace('/', '_') or 'portada')}-{name}.png"
                    await page.screenshot(path=str(fn), full_page=True)
            await ctx.close()
        await b.close()
    print(f"Pàgines provades: {len(todo)} (ordinador i mòbil)")
    print(f"Problemes: {len(problems)}")
    for x in problems:
        print(" -", x)
    print(f"Enllaços interns que no porten enlloc: {len(bad_links)}")
    for x in sorted(bad_links):
        print(" -", x)


if __name__ == "__main__":
    asyncio.run(main())
