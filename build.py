#!/usr/bin/env python3
"""Genera la web estàtica de L'Espiral (lespiral.cat) a la carpeta docs/.

Ús:  python3 build.py [--nomes adreça,adreça,...]

El mateix sistema que espiralosona.com i elarasocial.com (dades en JSON, plantilles Jinja, un sol full d'estils),
adaptat a una web que ve d'un WordPress i que ha de conservar-ne les adreces i el SEO:

- data/site.json: nom, adreça pública (publish), menú, contacte, punt del mapa (geo), dades per a Google
  (organization), ressenyes, peu, arxius (categoria i etiquetes) i adreces antigues (redirects).
- data/pages/<adreça>.json: una pàgina per fitxer (la portada és data/pages/index.json). Es publica a /<adreça>/.
- data/articles/<adreça>.json: un article (entrada del WordPress) per fitxer. Es publica a /<adreça>/.
- data/media.json: la biblioteca de mitjans (mides i text alternatiu de cada imatge).
- static/: es copia tal qual a docs/ (les imatges i PDF originals a wp-content/uploads/, els fitxers de verificació
  de Google, llms.txt).

Les adreces internes de les dades s'escriuen com a la web: "/contacto-3/". En generar, s'hi posa l'arrel de
la web (/lespiral/ a l'adreça de proves de GitHub, / amb el domini).

Amb --nomes, només es generen aquestes pàgines (per revisar-les abans de fer la resta).
"""
import email.utils, html, json, math, re, shutil, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

ROOT = Path(__file__).resolve().parent
DATA, SRC, OUT, STATIC = ROOT / "data", ROOT / "src", ROOT / "docs", ROOT / "static"
UPLOADS = STATIC / "wp-content" / "uploads"
ICONS = json.loads((SRC / "icons.json").read_text(encoding="utf-8"))

errors, warnings = [], []
site = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
media = json.loads((DATA / "media.json").read_text(encoding="utf-8")) if (DATA / "media.json").exists() else {}
SITE_URL = site["site_url"].rstrip("/") + "/"           # l'adreça definitiva (canònic, mapes del web, dades per a Google)
PUBLISH = site["publish"]["url"].rstrip("/") + "/"       # on es publica ara
BASE = urlparse(PUBLISH).path or "/"                       # /lespiral/ a GitHub Pages, / amb el domini
NOINDEX = not site["publish"].get("index", False)

ONLY = None
if "--nomes" in sys.argv:
    ONLY = {p.strip("/") for p in sys.argv[sys.argv.index("--nomes") + 1].split(",")}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESOS = ["gener", "febrer", "març", "abril", "maig", "juny", "juliol", "agost", "setembre", "octubre", "novembre", "desembre"]


def fecha(iso, lang="es"):
    y, m, d = (int(x) for x in iso[:10].split("-"))
    if lang == "ca":
        mes = MESOS[m - 1]
        return f"{d} {'d’' if mes[0] in 'ao' else 'de '}{mes} de {y}"
    return f"{d} de {MESES[m - 1]} de {y}"


# ---------------------------------------------------------------- adreces i imatges

def u(href):
    """Adreça de les dades → adreça a la web publicada. "/x/" → BASE + "x/"; la resta (http, mailto, tel, #) igual."""
    if href is None:
        return None
    if href.startswith("/") and not href.startswith("//"):
        return BASE + href[1:]
    return href


def canonical(path):
    return SITE_URL + (quote(path, safe="/").lower().replace("%2f", "/") + "/" if path else "")


def img_info(path):
    """Imatge de la biblioteca ("2023/05/x.jpg") → src, srcset, width, height (com WordPress)."""
    m = media.get(path)
    src = u("/wp-content/uploads/" + path)
    info = {"src": src, "srcset": "", "width": None, "height": None, "exists": (UPLOADS / path).exists()}
    if not info["exists"]:
        warnings.append(f"falta la imatge wp-content/uploads/{path}")
    if m:
        info["width"], info["height"] = m.get("w"), m.get("h")
        cands = [(s[0], s[1]) for s in m.get("sizes", []) if (UPLOADS / s[0]).exists()
                 and m.get("w") and m.get("h") and s[2] and abs(s[1] / s[2] - m["w"] / m["h"]) < 0.02]
        if cands and m.get("w"):
            cands.append((path, m["w"]))
            info["srcset"] = ", ".join(f"{u('/wp-content/uploads/' + f)} {w}w" for f, w in sorted(set(cands), key=lambda x: x[1]))
    return info


def media_by_url(src):
    mm = re.search(r"/wp-content/uploads/([^\"'?#]+)", src)
    if not mm:
        return None, None
    path = mm.group(1)
    if path in media:
        return path, media[path]
    # mida reduïda: foto-1024x683.jpg
    base = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", path)
    return (base, media[base]) if base in media else (path, None)


IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)


def fix_html(h):
    """HTML de les dades → HTML de la web: adreces amb l'arrel, i les imatges amb mides i càrrega diferida."""
    if not h:
        return Markup("")
    h = re.sub(r'(href|src|poster)="(/[^"/][^"]*|/)"', lambda m: f'{m.group(1)}="{u(m.group(2))}"', h)
    h = re.sub(r'srcset="([^"]*)"', lambda m: 'srcset="' + re.sub(r"(^|,\s*)(/)(?!/)", lambda x: x.group(1) + BASE, m.group(1)) + '"', h)

    def one(m):
        tag = m.group(0)
        srcm = re.search(r'\ssrc="([^"]+)"', tag)
        if not srcm:
            return tag
        path, info = media_by_url(srcm.group(1))
        add = []
        if " loading=" not in tag:
            add.append('loading="lazy"')
        if " decoding=" not in tag:
            add.append('decoding="async"')
        if info and " width=" not in tag and " height=" not in tag:
            full = path == re.search(r"/wp-content/uploads/([^\"'?#]+)", srcm.group(1)).group(1)
            if full and info.get("w"):
                add.append(f'width="{info["w"]}" height="{info["h"]}"')
            else:
                d = re.search(r"-(\d+)x(\d+)\.\w+$", srcm.group(1))
                if d:
                    add.append(f'width="{d.group(1)}" height="{d.group(2)}"')
        if " alt=" not in tag:
            add.append('alt=""')
        if not add:
            return tag
        return re.sub(r"\s*/?>$", " " + " ".join(add) + ">", tag)
    h = IMG_TAG.sub(one, h)
    return Markup(h)


def icon(name, cls=None):
    if name not in ICONS:
        errors.append(f"la icona {name!r} no és a src/icons.json")
        return ""
    vb = ICONS.get(name + "__vb", "0 0 256 256")
    c = "i" + (" " + cls if cls else "")
    return Markup(f'<svg class="{c}" viewBox="{vb}" fill="currentColor" aria-hidden="true" focusable="false">{ICONS[name]}</svg>')


def plain(h, n=None):
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()
    if n:
        w = t.split()
        if len(w) > n:
            t = " ".join(w[:n]) + "…"
    return t


# ---------------------------------------------------------------- dades

def load_json(f):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"{f.relative_to(ROOT)}: el JSON no és correcte ({e})")
        return None


pages = [p for p in (load_json(f) for f in sorted((DATA / "pages").rglob("*.json"))) if p]
articles = [a for a in (load_json(f) for f in sorted((DATA / "articles").glob("*.json"))) if a]
articles.sort(key=lambda a: (a["published"], a.get("wp_id", 0)), reverse=True)
for a in articles:
    a["date_text"] = fecha(a["published"], a.get("lang", "es"))
    a["summary"] = plain(a["html"], 28)
    a["url"] = "/" + a["path"] + "/"
paths = {p["path"] for p in pages} | {a["path"] for a in articles}
by_path = {p["path"]: p for p in pages}
for p in pages:
    p["url"] = "/" + p["path"] + "/" if p["path"] else "/"


# Comprovacions: les adreces internes de les dades porten a una pàgina que existeix
def internal_targets():
    out = set()
    for p in paths:
        out.add("/" + p + "/" if p else "/")
    return out


# ---------------------------------------------------------------- dades estructurades (com Rank Math)

def json_ld(kind, path, title, description, lang, published, modified, image=None, keyword=None, headline=None):
    url = canonical(path)
    org_id, place_id, site_id = SITE_URL + "#organization", SITE_URL + "#place", SITE_URL + "#website"
    c, g, o = site["contact"], site["geo"], site["organization"]
    address = {"@type": "PostalAddress", "streetAddress": c["address"], "addressLocality": c["city"],
               "addressRegion": c["region"], "postalCode": c["postal_code"], "addressCountry": c["country"]}
    graph = [
        {"@type": "Place", "@id": place_id, "address": address,
         "geo": {"@type": "GeoCoordinates", "latitude": g["lat"], "longitude": g["lng"]},
         "hasMap": f"https://www.google.com/maps/search/?api=1&query={g['lat']},{g['lng']}"},
        {"@type": "Organization", "@id": org_id, "name": o["name"], "url": SITE_URL.rstrip("/"), "email": o["email"],
         "address": address, "telephone": o["telephone"], "location": {"@id": place_id},
         "logo": {"@type": "ImageObject", "@id": SITE_URL + "#logo", "url": SITE_URL + o["logo"], "caption": o["name"], "inLanguage": "es"},
         **({"sameAs": o["same_as"]} if o.get("same_as") else {})},
        {"@type": "WebSite", "@id": site_id, "url": SITE_URL.rstrip("/"), "name": site["name"], "publisher": {"@id": org_id}, "inLanguage": "es"},
    ]
    page = {"@type": "CollectionPage" if kind == "archive" else "WebPage", "@id": url + "#webpage", "url": url, "name": title,
            "isPartOf": {"@id": site_id}, "inLanguage": lang}
    if published:
        page["datePublished"], page["dateModified"] = published, modified or published
    if path == "":
        page["about"] = {"@id": org_id}
    if image:
        img_url = SITE_URL + "wp-content/uploads/" + image
        m = media.get(image) or {}
        graph.append({"@type": "ImageObject", "@id": img_url, "url": img_url, **({"width": m["w"], "height": m["h"]} if m.get("w") else {}), "inLanguage": lang})
        page["primaryImageOfPage"] = {"@id": img_url}
    graph.append(page)
    if kind in ("page", "article"):
        a = site["author"]
        person_id = SITE_URL + "#" + a["id"]
        graph.append({"@type": "Person", "@id": person_id, "name": a["name"], "worksFor": {"@id": org_id}})
        art = {"@type": "BlogPosting" if kind == "article" else "Article", "@id": url + "#richSnippet", "headline": headline or title,
               "description": description or None, "datePublished": published, "dateModified": modified or published,
               "author": {"@id": person_id, "name": a["name"]}, "publisher": {"@id": org_id},
               "isPartOf": {"@id": url + "#webpage"}, "mainEntityOfPage": {"@id": url + "#webpage"}, "inLanguage": lang}
        if keyword:
            art["keywords"] = keyword
        if image:
            art["image"] = {"@id": SITE_URL + "wp-content/uploads/" + image}
        graph.append({k: v for k, v in art.items() if v})
    return Markup(json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</", "<\\/"))


# ---------------------------------------------------------------- plantilles

def card_like(col):
    ts = [b["t"] for b in col]
    return "img" in ts and "h" in ts


def row_kind(cols):
    if len(cols) == 1:
        return "single"
    if len(cols) >= 2 and all(card_like(c) for c in cols):
        return "cards"
    if len(cols) == 2:
        only_img = [all(b["t"] == "img" for b in c) for c in cols]
        if any(only_img) and not all(only_img):
            return "split-img-right" if only_img[1] else "split-img-left"
    return "cols"


def first_section_is_head(p):
    s = (p.get("sections") or [None])[0]
    if not s:
        return False
    blocks = [b for c in s["cols"] for b in c]
    # La capçalera: la primera franja si té foto de fons, o si és d'una sola columna i porta l'H1
    return bool(s.get("bg")) or (len(s["cols"]) == 1 and any(b["t"] == "h" and b.get("tag") == "h1" for b in blocks))


def group_buttons(blocks):
    """Botons seguits → un sol grup (van a la mateixa línia)."""
    out = []
    for b in blocks:
        if b["t"] == "btn":
            if out and out[-1]["t"] == "btns":
                out[-1]["items"].append(b)
            else:
                out.append({"t": "btns", "items": [b]})
        else:
            out.append(b)
    return out


def assign_bands(p):
    """Color de cada franja: capçalera, foto de fons, fosca, o blanc i blau clar alternats."""
    alt = 0
    for i, s in enumerate(p.get("sections") or []):
        if i == 0 and first_section_is_head(p):
            s["_band"] = "head"
        elif s.get("bg"):
            s["_band"] = "photo"
        elif s.get("tone") == "dark":
            s["_band"] = "dark"
        else:
            s["_band"] = "soft" if alt % 2 else "white"
            alt += 1


def simple_autop(t):
    return "".join(f"<p>{x.strip()}</p>" for x in re.split(r"\n\s*\n", t or "") if x.strip())


env = Environment(loader=FileSystemLoader(SRC / "templates"), autoescape=select_autoescape(["html", "xml"]), trim_blocks=True, lstrip_blocks=True)
env.filters.update(u=u, fix=fix_html, plain=plain, fecha=fecha, row_kind=row_kind, group_buttons=group_buttons, wpautop=simple_autop)
env.globals.update(icon=icon, img_info=img_info, site=site, noindex=NOINDEX, base=BASE, version=str(int(time.time())),
                   articles=articles, by_path=by_path, Markup=Markup)

REVIEWS_MARK = "<div data-ressenyes></div>"


def with_reviews(h):
    """Al lloc on hi havia el requadre de Trustindex, l'espai de ressenyes (decisió 7)."""
    if REVIEWS_MARK not in str(h):
        return h
    r = env.get_template("parts.html").module.reviews()
    return Markup(str(h).replace(REVIEWS_MARK, str(r)))


env.filters["with_reviews"] = with_reviews
for p in pages:
    assign_bands(p)

PAGES_DONE = []


def render(template, path, **ctx):
    """path: "" (portada), "contacto-3", "category/articulos/page/2"... o un fitxer ("404.html")."""
    is_file = path.endswith(".html") or path.endswith(".xml") or path.endswith(".txt")
    out = env.get_template(template).render(path=path, canonical=None if is_file else canonical(path), **ctx)
    dest = OUT / path if is_file else OUT / path / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    PAGES_DONE.append(path)
    return out


def want(path):
    return ONLY is None or path in ONLY


if errors:
    print("No s'ha generat la web. Cal arreglar:", *("- " + e for e in errors), sep="\n")
    sys.exit(1)

# docs/ es torna a fer cada vegada; static/ (imatges originals) s'hi copia només si ha canviat
if OUT.exists():
    for x in OUT.iterdir():
        if x.name != "wp-content":
            shutil.rmtree(x) if x.is_dir() else x.unlink()
OUT.mkdir(exist_ok=True)
n_static = 0
for f in STATIC.rglob("*"):
    if f.is_file():
        d = OUT / f.relative_to(STATIC)
        if not d.exists() or d.stat().st_size != f.stat().st_size:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, d)
            n_static += 1

pending = 0
for p in pages:
    if not want(p["path"]):
        continue
    lang = p.get("lang", "es")
    tpl = "home.html" if p["path"] == "" else "page.html"
    head = first_section_is_head(p)
    out = render(tpl, p["path"], page=p, lang=lang, head=head, paged=None, page_title=p.get("seo_title") or p["title"],
                 description=p.get("description"), og_type="website" if p["path"] == "" else "article",
                 og_image=p.get("og_image"), ld=json_ld("page", p["path"], p.get("seo_title") or p["title"], p.get("description"), lang,
                 p.get("published"), p.get("modified"), p.get("image"), p.get("keyword"), p.get("title")))
    pending += out.count("[PENDENT]")
    # /articulos/: el llistat té paginació (/articulos/page/2/...), 9 per pàgina, com ara
    for s in p.get("sections") or []:
        for b in [b for c in s["cols"] for b in c]:
            if b["t"] == "articles" and b.get("paginated"):
                n = b["n"]
                total = math.ceil(len(articles) / n)
                for k in range(2, total + 1):
                    render("page.html", f"{p['path']}/page/{k}", page=p, lang=lang, head=head, page_title=p.get("seo_title") or p["title"],
                           description=p.get("description"), og_type="article", og_image=p.get("og_image"), paged=k,
                           ld=json_ld("page", f"{p['path']}/page/{k}", p.get("seo_title") or p["title"], p.get("description"), lang,
                                      p.get("published"), p.get("modified"), p.get("image")))

for i, a in enumerate(articles):
    if not want(a["path"]):
        continue
    lang = a.get("lang", "es")
    newer = articles[i - 1] if i > 0 else None
    older = articles[i + 1] if i + 1 < len(articles) else None
    out = render("article.html", a["path"], article=a, lang=lang, page_title=a.get("seo_title") or a["title"],
                 description=a.get("description"), og_type="article", og_image=a.get("og_image"), newer=newer, older=older,
                 ld=json_ld("article", a["path"], a.get("seo_title") or a["title"], a.get("description"), lang,
                            a["published"], a.get("modified"), a.get("image"), a.get("keyword"), a["title"]))
    pending += out.count("[PENDENT]")

# Arxius: /category/articulos/ (10 per pàgina) i /tag/<etiqueta>/, amb paginació, com ara
arch = site["archives"]
groups = [("category/" + arch["category"]["slug"], arch["category"]["name"], [a for a in articles if arch["category"]["slug"] in a.get("categories", [])], None)]
for slug, name in arch["tags"].items():
    groups.append(("tag/" + slug, name, [a for a in articles if slug in a.get("tags", [])], arch.get("tag_descriptions", {}).get(slug)))
for base_path, name, items, desc in groups:
    per = arch["category"]["per_page"]
    total = max(1, math.ceil(len(items) / per))
    for k in range(1, total + 1):
        path = base_path if k == 1 else f"{base_path}/page/{k}"
        if not want(path) and ONLY is not None:
            continue
        title = f"Arxius de {name} - L'Espiral" if k == 1 else f"Arxius de {name} - Página {k} de {total} - L'Espiral"
        render("archive.html", path, lang="es", page_title=title, description=None, og_type="article", name=name, desc=desc,
               items=items[(k - 1) * per:k * per], k=k, total=total, base_path=base_path,
               ld=json_ld("archive", path, title, None, "es", None, None))

render("404.html", "404.html", lang="es", page_title="Página no encontrada - L'Espiral", description=None, og_type="website", ld=None)

# Adreces antigues: porten a la nova a l'instant (GitHub Pages no fa redireccions 301)
REDIRECT = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="robots" content="noindex">
<title>L'Espiral</title><link rel="canonical" href="{canon}"><meta http-equiv="refresh" content="0; url={to}">
</head><body><p>Esta página ha cambiado de dirección: <a href="{to}">{canon}</a></p></body></html>
"""
n_red = 0
for old, to in site.get("redirects", {}).items():
    old = old.strip("/")
    if old in paths:
        errors.append(f"data/site.json (redirects): /{old}/ és una pàgina de la web; no pot portar a una altra")
        continue
    target = to.strip("/")
    if not to.startswith("http") and target.split("#")[0] not in paths and target.split("/page/")[0] not in {g[0] for g in groups}:
        errors.append(f"data/site.json (redirects): /{old}/ porta a {to}, que no existeix")
        continue
    if ONLY is not None and target.split("#")[0] not in ONLY:
        continue
    dest = OUT / old / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(REDIRECT.format(to=html.escape(u(to)), canon=html.escape(SITE_URL + to.lstrip("/"))), encoding="utf-8")
    n_red += 1

# Feeds RSS: /feed/ i /category/articulos/feed/ (els 10 últims articles, com WordPress)
def rss(path, title, link, items):
    now = email.utils.format_datetime(datetime.now(timezone.utc))
    out = env.get_template("feed.xml").render(title=title, link=link, items=items[:10], self_url=SITE_URL + path + "/", now=now,
                                              pubdate=lambda d: email.utils.format_datetime(datetime.fromisoformat(d[:10]).replace(tzinfo=timezone.utc)),
                                              absolute=lambda h: Markup(re.sub(r'(href|src)="/(?!/)', lambda m: f'{m.group(1)}="{SITE_URL}', h)))
    d = OUT / path / "index.html"
    d.parent.mkdir(parents=True, exist_ok=True)
    d.write_text(out, encoding="utf-8")


if ONLY is None:
    rss("feed", site["name"], SITE_URL.rstrip("/"), articles)
    rss("category/articulos/feed", f"{site['name']} » Artículos", SITE_URL + "category/articulos/", articles)

# Mapes del web amb els mateixos noms que ara: sitemap_index.xml, post-sitemap.xml i page-sitemap.xml
def images_of(obj):
    found = []
    if obj.get("image"):
        found.append(obj["image"])
    blob = json.dumps(obj.get("sections") or []) + (obj.get("html") or "")
    for m in re.finditer(r'(?:"src": "|/wp-content/uploads/)([0-9]{4}/[0-9]{2}/[^"\s<>?#]+?\.(?:jpe?g|png|webp|gif))', blob, re.I):
        p = m.group(1)
        if p not in found:
            found.append(p)
    return found


def sitemap(name, entries):
    rows = []
    for loc, lastmod, imgs in entries:
        im = "".join(f"\n\t\t<image:image>\n\t\t\t<image:loc>{escape(SITE_URL + 'wp-content/uploads/' + quote(i))}</image:loc>\n\t\t</image:image>" for i in imgs)
        rows.append(f"\t<url>\n\t\t<loc>{escape(loc)}</loc>\n\t\t<lastmod>{lastmod}</lastmod>{im}\n\t</url>")
    (OUT / name).write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                            'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1" '
                            'xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd '
                            'http://www.google.com/schemas/sitemap-image/1.1 http://www.google.com/schemas/sitemap-image/1.1/sitemap-image.xsd" '
                            'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n", encoding="utf-8")


if ONLY is None:
    post_entries = [(canonical(a["path"]), a.get("modified") or a["published"], images_of(a)) for a in articles]
    page_entries = [(canonical(p["path"]), p.get("modified") or p.get("published"), images_of(p))
                    for p in sorted(pages, key=lambda p: (p["path"] != "", p.get("modified") or ""), reverse=False)]
    sitemap("post-sitemap.xml", post_entries)
    sitemap("page-sitemap.xml", page_entries)
    last_post = max(e[1] for e in post_entries)
    last_page = max(e[1] for e in page_entries)
    (OUT / "sitemap_index.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"\t<sitemap>\n\t\t<loc>{SITE_URL}post-sitemap.xml</loc>\n\t\t<lastmod>{last_post}</lastmod>\n\t</sitemap>\n"
        f"\t<sitemap>\n\t\t<loc>{SITE_URL}page-sitemap.xml</loc>\n\t\t<lastmod>{last_page}</lastmod>\n\t</sitemap>\n"
        "</sitemapindex>\n", encoding="utf-8")

(OUT / "assets").mkdir(exist_ok=True)
shutil.copy(SRC / "site.css", OUT / "assets" / "site.css")
shutil.copy(SRC / "site.js", OUT / "assets" / "site.js")
shutil.copytree(SRC / "img", OUT / "assets" / "img", dirs_exist_ok=True)
(OUT / ".nojekyll").write_text("")
if NOINDEX:
    (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
else:
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap_index.xml\n")
if (ROOT / "CNAME").exists():
    shutil.copy(ROOT / "CNAME", OUT / "CNAME")

# Enllaços interns de les dades que no porten enlloc
known = internal_targets() | {"/" + o.strip("/") + "/" for o in site.get("redirects", {})} | {"/" + g[0] + "/" for g in groups} | {"/feed/", "/category/articulos/feed/"}
broken = set()
for f in OUT.rglob("index.html"):
    for m in re.finditer(r'href="' + re.escape(BASE) + r'([^"#?]*)', f.read_text(encoding="utf-8")):
        tgt = m.group(1)
        if tgt.startswith(("wp-content/", "assets/")) or tgt.endswith((".pdf", ".xml", ".txt", ".html", ".jpg", ".png")):
            if not (OUT / tgt).exists():
                broken.add((f.parent.relative_to(OUT).as_posix(), "/" + tgt))
            continue
        t = "/" + tgt if tgt else "/"
        if not t.endswith("/") and "." not in t.rsplit("/", 1)[-1]:
            t += "/"          # GitHub Pages porta /adreça a /adreça/ tot sol
        t = re.sub(r"/page/\d+/$", "/", t)
        if t not in known:
            broken.add((f.parent.relative_to(OUT).as_posix(), t))

if errors:
    print("Cal arreglar:", *("- " + e for e in errors), sep="\n")
    sys.exit(1)
print(f"Fet: {len(PAGES_DONE)} pàgines generades; {n_red} adreces antigues redirigides; {n_static} fitxers copiats de static/; "
      f"{pending} marques [PENDENT]. adreça={PUBLISH} cercadors={'no' if NOINDEX else 'sí'}")
if broken:
    print(f"Enllaços interns que no porten enlloc ({len(broken)}):")
    for src, t in sorted(broken)[:60]:
        print(f"  /{src}/ → {t}")
for w in sorted(set(warnings))[:20]:
    print("Avís:", w)
