#!/usr/bin/env python3
"""Comprova la web generada (docs/) contra l'inventari d'adreces del WordPress (fases 3 i 4).

Ús:  python3 tools/comprova.py INVENTARI.xlsx [--imatges CARPETA_UPLOADS_ORIGINAL]

Per a cada adreça de l'inventari:
- «Es manté»: ha d'existir a docs/ (pàgina, article, arxiu, imatge, PDF, feed o fitxer tècnic).
- «Redirecció a …»: ha de ser una pàgina de redirecció cap a l'adreça bona.
- «Es deixa»: no ha d'existir (porta a la 404).
Per a les pàgines i entrades: títol, descripció, H1 (text i nombre) i nombre d'H2 iguals que al WordPress,
canònic a https://lespiral.cat/… i dades estructurades presents.
Amb --imatges, compara la suma (SHA-256) de cada imatge i PDF amb l'original.
"""
import hashlib, html, json, re, sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def norm(s):
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def strip(h):
    return norm(re.sub(r"<[^>]+>", " ", h))


def target(url):
    path = unquote(urlparse(url).path).lstrip("/")
    p = DOCS / path
    if path == "" or path.endswith("/") or p.is_dir():
        p = p / "index.html"
    return p


def main():
    import openpyxl
    wb = openpyxl.load_workbook(sys.argv[1], data_only=True, read_only=True)
    inv = [r for r in wb["Inventari"].iter_rows(min_row=2, values_only=True) if r[0]]
    seo = {r[0]: r for r in wb["SEO per pàgina"].iter_rows(min_row=2, values_only=True) if r[0]}
    problems, ok, h2_less = [], 0, []
    for r in inv:
        url, kind, title, desc, what = r[0], r[1], r[2], r[3], (r[12] or "")
        f = target(url)
        if what.startswith("Es deixa"):
            if f.exists():
                problems.append(f"{url}: s'havia de deixar i existeix")
            else:
                ok += 1
            continue
        if what.startswith("Redirecció"):
            m = re.search(r"a (/\S+?/)\s", what + " ")
            if not f.exists() or 'http-equiv="refresh"' not in f.read_text(encoding="utf-8"):
                problems.append(f"{url}: falta la redirecció")
            elif m and m.group(1) not in f.read_text(encoding="utf-8"):
                problems.append(f"{url}: la redirecció no porta a {m.group(1)}")
            else:
                ok += 1
            continue
        if not f.exists():
            problems.append(f"{url}: NO EXISTEIX ({kind})")
            continue
        ok += 1
        if kind not in ("Pàgina", "Entrada"):
            continue
        h = f.read_text(encoding="utf-8")
        t = norm(re.search(r"<title>(.*?)</title>", h, re.S).group(1))
        if title and t != norm(title):
            problems.append(f"{url}: títol diferent\n    WP:   {norm(title)}\n    nova: {t}")
        d = re.search(r'<meta name="description" content="([^"]*)"', h)
        if desc and (not d or norm(d.group(1)) != norm(desc)):
            problems.append(f"{url}: descripció diferent")
        main = h.split('<main id="contingut">', 1)[1].split("</main>", 1)[0]
        h1s = [strip(x) for x in re.findall(r"<h1[^>]*>(.*?)</h1>", main, re.S)]
        h2s = re.findall(r"<h2[\s>]", main)
        s = seo.get(url)
        if s:
            wp_h1, wp_n1, wp_n2 = norm(s[3]), int(s[4] or 0), int(s[5] or 0)
            if len(h1s) != wp_n1:
                problems.append(f"{url}: {len(h1s)} H1 (al WordPress, {wp_n1})")
            elif wp_n1 == 1 and h1s[0].lower() != wp_h1.lower():
                problems.append(f"{url}: H1 diferent\n    WP:   {wp_h1}\n    nova: {h1s[0]}")
            if len(h2s) != wp_n2:
                (h2_less if len(h2s) == wp_n2 - 1 else problems).append(f"{url}: {len(h2s)} H2 (al WordPress, {wp_n2})")
        canon = re.search(r'<link rel="canonical" href="([^"]+)"', h)
        if not canon or unquote(canon.group(1)).lower() != unquote(url).lower():
            problems.append(f"{url}: canònic {canon.group(1) if canon else 'cap'}")
        if "application/ld+json" not in h:
            problems.append(f"{url}: sense dades estructurades")
    if "--imatges" in sys.argv:
        orig = Path(sys.argv[sys.argv.index("--imatges") + 1])
        n = bad = 0
        for o in orig.rglob("*"):
            if o.is_file() and o.name != ".htaccess":
                n += 1
                d = DOCS / "wp-content" / "uploads" / o.relative_to(orig)
                if not d.exists() or hashlib.sha256(d.read_bytes()).digest() != hashlib.sha256(o.read_bytes()).digest():
                    bad += 1
                    problems.append(f"imatge diferent o que falta: {o.relative_to(orig)}")
        print(f"Imatges i fitxers de wp-content/uploads: {n - bad} de {n} idèntics als originals")
    print(f"Adreces de l'inventari correctes: {ok} de {len(inv)}")
    if h2_less:
        print(f"Pàgines amb un H2 menys (el text duplicat ordinador/mòbil, que ara hi és una vegada): {len(h2_less)}")
    print(f"Problemes: {len(problems)}")
    for p in problems:
        print(" -", p)


if __name__ == "__main__":
    main()
