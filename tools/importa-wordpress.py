#!/usr/bin/env python3
"""Passa el contingut del WordPress de lespiral.cat a la carpeta data/ (una sola vegada, a la fase 3).

Ús:  python3 tools/importa-wordpress.py EXPORTACIO.xml INVENTARI.xlsx [--nomes adreça,adreça,...]

- EXPORTACIO.xml: l'exportació de WordPress (Eines › Exporta) de la còpia de seguretat del 8/11/2026.
- INVENTARI.xlsx: el full «Inventari d'adreces de lespiral.cat» descarregat en format Excel.
  D'aquí surten el títol i la descripció per a Google, l'idioma, les dates, la paraula clau i l'H1 de cada adreça,
  tal com els mostrava el WordPress.

Escriu:
- data/pages/<adreça>.json: les 50 pàgines publicades (la portada és data/pages/index.json).
  Les pàgines d'Elementor es guarden com a seccions (files i columnes amb blocs: encapçalaments, text, imatges,
  botons, llistes...). Es manté el text tal com és, amb les mateixes etiquetes (h1, h2, p...).
- data/articles/<adreça>.json: les 143 entrades publicades, amb el seu HTML.
- data/media.json: la biblioteca de mitjans (fitxer, mida, text alternatiu i mides reduïdes de cada imatge).

Ni l'exportació ni l'inventari es desen al repositori: l'exportació conté comentaris i adreces de correu.
No s'importen els esborranys (decisió 17), els comentaris (decisió 6) ni els formularis (decisió 5).
Després d'importar, el contingut es corregeix directament als fitxers de data/.
"""
import html, json, re, sys, unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = "https://lespiral.cat"
NS = {"wp": "http://wordpress.org/export/1.2/", "content": "http://purl.org/rss/1.0/modules/content/",
      "excerpt": "http://wordpress.org/export/1.2/excerpt/", "dc": "http://purl.org/dc/elements/1.1/"}


# ---------------------------------------------------------------- lectura

def php_unserialize(s):
    """Prou per llegir _wp_attachment_metadata (arrays, cadenes, enters, decimals, booleans, null)."""
    b = s.encode("utf-8")
    pos = 0

    def read():
        nonlocal pos
        t = chr(b[pos])
        if t == "N":
            pos += 2
            return None
        if t in "ibd":
            end = b.index(b";", pos)
            v = b[pos + 2:end].decode()
            pos = end + 1
            return int(v) if t == "i" else (v == "1" if t == "b" else float(v))
        if t == "s":
            colon = b.index(b":", pos + 2)
            n = int(b[pos + 2:colon])
            v = b[colon + 2:colon + 2 + n].decode("utf-8", "replace")
            pos = colon + 2 + n + 2
            return v
        if t == "a":
            colon = b.index(b":", pos + 2)
            n = int(b[pos + 2:colon])
            pos = colon + 2
            out = {}
            for _ in range(n):
                k = read()
                out[k] = read()
            pos += 1
            return out
        raise ValueError(f"tipus PHP desconegut {t!r} a {pos}")

    return read()


def load_xml(path):
    ch = ET.parse(path).getroot().find("channel")
    items = []
    for i in ch.findall("item"):
        def g(p):
            e = i.find(p, NS)
            return e.text if e is not None else None
        d = dict(title=g("title") or "", link=g("link"), id=int(g("wp:post_id")), type=g("wp:post_type"),
                 status=g("wp:status"), slug=g("wp:post_name"), parent=int(g("wp:post_parent") or 0),
                 date=g("wp:post_date"), modified=g("wp:post_modified"), content=g("content:encoded") or "",
                 excerpt=g("excerpt:encoded") or "", url=g("wp:attachment_url"),
                 cats=[(c.get("domain"), c.get("nicename"), c.text) for c in i.findall("category")])
        d["meta"] = {m.find("wp:meta_key", NS).text: m.find("wp:meta_value", NS).text for m in i.findall("wp:postmeta", NS)}
        items.append(d)
    return items


def load_inventory(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    inv, seo = {}, {}
    for r in wb["Inventari"].iter_rows(min_row=2, values_only=True):
        if r[0]:
            inv[norm_url(r[0])] = r
    for r in wb["SEO per pàgina"].iter_rows(min_row=2, values_only=True):
        if r[0]:
            seo[norm_url(r[0])] = r
    return inv, seo


def norm_url(u):
    return unquote(u.strip()).lower()


# ---------------------------------------------------------------- HTML

BLOCK = r"(?:table|thead|tfoot|caption|col|colgroup|tbody|tr|td|th|div|dl|dd|dt|ul|ol|li|pre|form|map|area|blockquote|address|math|style|p|h[1-6]|hr|fieldset|legend|section|article|aside|hgroup|header|footer|nav|figure|figcaption|details|menu|summary)"


def wpautop(text, br=True):
    """Port de wpautop() de WordPress: paràgrafs a partir dels salts de línia (entrades i text d'Elementor)."""
    if not text.strip():
        return ""
    pre = {}
    if "<pre" in text:
        def keep(m):
            k = f"<pre wp-pre-tag-{len(pre)}></pre>"
            pre[k] = m.group(0)
            return k
        text = re.sub(r"<pre[^>]*>.*?</pre>", keep, text, flags=re.S)
    text = text + "\n"
    text = re.sub(r"<br\s*/?>\s*<br\s*/?>", "\n\n", text)
    text = re.sub(r"(<" + BLOCK + r"[\s/>])", r"\n\n\1", text)
    text = re.sub(r"(</" + BLOCK + r">)", r"\1\n\n", text)
    text = re.sub(r"<hr\s*?/?>", "<hr />\n\n", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s*<option", "<option", text)
    text = re.sub(r"</option>\s*", "</option>", text)
    text = re.sub(r"\n\n+", "\n\n", text)
    pees = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    text = "".join("<p>" + p.strip("\n") + "</p>\n" for p in pees)
    text = re.sub(r"<p>\s*</p>", "", text)
    text = re.sub(r"<p>([^<]+)</(div|address|form)>", r"<p>\1</p></\2>", text)
    text = re.sub(r"<p>\s*(</?" + BLOCK + r"[^>]*>)\s*</p>", r"\1", text)
    text = re.sub(r"<p>(<li.+?)</p>", r"\1", text)
    text = re.sub(r"<p><blockquote([^>]*)>", r"<blockquote\1><p>", text, flags=re.I)
    text = text.replace("</blockquote></p>", "</p></blockquote>")
    text = re.sub(r"<p>\s*(</?" + BLOCK + r"[^>]*>)", r"\1", text)
    text = re.sub(r"(</?" + BLOCK + r"[^>]*>)\s*</p>", r"\1", text)
    if br:
        text = re.sub(r"<(script|style|svg).*?</\1>", lambda m: m.group(0).replace("\n", "<WPPreserveNewline />"), text, flags=re.S)
        text = re.sub(r"(?<!<br />)\s*\n", "<br />\n", text)
        text = text.replace("<WPPreserveNewline />", "\n")
    text = re.sub(r"(</?" + BLOCK + r"[^>]*>)\s*<br />", r"\1", text)
    text = re.sub(r"<br />(\s*</?(?:p|li|div|dl|dd|dt|th|pre|td|ul|ol)[^>]*>)", r"\1", text)
    text = re.sub(r"\n</p>$", "</p>", text)
    for k, v in pre.items():
        text = text.replace(k, v)
    return text.strip()


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def tidy(s):
    """Text d'un camp d'Elementor: els salts de línia no es veuen a la web (són espais)."""
    s = (s or "").replace("\r", "")
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)
    return re.sub(r"  +", " ", s).strip()


def local_url(u):
    """https://lespiral.cat/xxx → /xxx (la plantilla hi posa l'arrel de la web)."""
    if not u:
        return u
    u = u.strip()
    m = re.match(r"^https?://(?:www\.)?lespiral\.cat(/.*)?$", u, re.I)
    if m:
        return m.group(1) or "/"
    return u


def fix_links(h):
    """Dins d'un HTML: enllaços i imatges a lespiral.cat passen a adreces de la web (/...)."""
    h = re.sub(r'(href|src|srcset)="https?://(?:www\.)?lespiral\.cat(/[^"]*)?"', lambda m: f'{m.group(1)}="{m.group(2) or "/"}"', h, flags=re.I)
    h = re.sub(r"(href|src)='https?://(?:www\.)?lespiral\.cat(/[^']*)?'", lambda m: f"{m.group(1)}='{m.group(2) or '/'}'", h, flags=re.I)
    h = re.sub(r'(srcset="[^"]*")', lambda m: re.sub(r"https?://(?:www\.)?lespiral\.cat/", "/", m.group(1)), h)
    return h


def youtube_nocookie(h):
    return re.sub(r"https?://(?:www\.)?youtube\.com/embed/", "https://www.youtube-nocookie.com/embed/", h)


def shortcodes(h):
    """[caption] → figura amb peu; [trustindex] → espai de ressenyes (decisió 7); [gtranslate] fora (decisió 1)."""
    def cap(m):
        inner = m.group(2).strip()
        mm = re.match(r"^((?:<a[^>]*>\s*)?<img[^>]*>(?:\s*</a>)?)(.*)$", inner, re.S)
        if not mm:
            return inner
        return f'<figure class="wp-caption">{mm.group(1)}<figcaption>{mm.group(2).strip()}</figcaption></figure>'
    h = re.sub(r"\[caption([^\]]*)\](.*?)\[/caption\]", cap, h, flags=re.S)
    h = re.sub(r"\[trustindex[^\]]*\]", '<div data-ressenyes></div>', h)
    h = re.sub(r"\[gtranslate[^\]]*\]", "", h)
    return h


def clean_post_html(raw):
    # Com WordPress: el contingut de blocs (Gutenberg) ja porta els paràgrafs; el de l'editor clàssic passa per wpautop
    blocks = "<!-- wp:" in raw
    h = re.sub(r"<!--\s*/?wp:.*?-->", "", raw, flags=re.S)
    if not blocks:
        h = wpautop(h)
    h = shortcodes(h)
    h = re.sub(r"<p>(\s|&nbsp;)*</p>", "", h)
    h = fix_links(h)
    h = youtube_nocookie(h)
    h = re.sub(r"\n{3,}", "\n\n", h).strip()
    return h


# ---------------------------------------------------------------- biblioteca de mitjans

def build_media(items):
    media = {}
    for a in items:
        if a["type"] != "attachment":
            continue
        file = a["meta"].get("_wp_attached_file") or ""
        meta = {}
        try:
            meta = php_unserialize(a["meta"].get("_wp_attachment_metadata") or "N;") or {}
        except Exception:
            pass
        sizes = []
        folder = file.rsplit("/", 1)[0] + "/" if "/" in file else ""
        for name, s in (meta.get("sizes") or {}).items():
            if isinstance(s, dict) and s.get("file"):
                sizes.append([folder + s["file"], s.get("width"), s.get("height")])
        alt = (a["meta"].get("_wp_attachment_image_alt") or "").strip()
        media[file] = {"id": a["id"], "w": meta.get("width"), "h": meta.get("height"),
                       # Elementor posa al text alternatiu el de la biblioteca; si no n'hi ha, el peu i, si no, el títol
                       "alt": alt, "alt_elementor": alt or strip_tags(a["excerpt"]) or html.unescape(a["title"] or ""),
                       "sizes": sorted({tuple(x) for x in sizes if x[1]}, key=lambda x: x[1])}
    return media


def upload_path(url):
    m = re.search(r"/wp-content/uploads/(.+)$", url or "")
    return unquote(m.group(1)) if m else None


# ---------------------------------------------------------------- Elementor → seccions

def hidden_desktop(st):
    """A la web d'ara, 40 textos hi són dues vegades: la versió d'ordinador (amagada al mòbil) i la del mòbil
    (amagada a l'ordinador), amb el mateix text. Ens quedem la del mòbil, que és la que Google llegeix."""
    return bool(st.get("hide_mobile")) and not st.get("hide_desktop")


def link_of(st, key="link"):
    l = st.get(key) or {}
    return local_url(l.get("url")) if isinstance(l, dict) and l.get("url") else None


def conv_widget(e, media, out):
    st = e.get("settings") or {}
    if hidden_desktop(st):
        return  # duplicats: a la web d'ara hi ha la versió d'ordinador i la del mòbil amb el mateix text
    w = e.get("widgetType")
    if w == "heading":
        txt = tidy(st.get("title"))
        if txt:
            b = {"t": "h", "tag": st.get("header_size") or "h2", "html": fix_links(txt)}
            if link_of(st):
                b["href"] = link_of(st)
            out.append(b)
    elif w == "text-editor":
        h = fix_links(youtube_nocookie(shortcodes(wpautop(st.get("editor") or ""))))
        if strip_tags(h) or "<img" in h or "<iframe" in h:
            out.append({"t": "text", "html": h})
    elif w == "image":
        im = st.get("image") or {}
        path = upload_path(im.get("url"))
        if path:
            m = media.get(path) or {}
            b = {"t": "img", "src": path, "alt": m.get("alt_elementor", im.get("alt", ""))}
            if st.get("link_to") == "custom" and link_of(st):
                b["href"] = link_of(st)
            elif st.get("link_to") == "file":
                b["href"] = "/wp-content/uploads/" + path
            if st.get("caption_source") == "custom" and st.get("caption"):
                b["caption"] = tidy(st["caption"])
            out.append(b)
    elif w == "button":
        out.append({"t": "btn", "text": tidy(st.get("text")) or "Click here", "href": link_of(st)})
    elif w == "icon-list":
        items = []
        for it in st.get("icon_list") or []:
            x = {"html": fix_links(tidy(it.get("text")))}
            if link_of(it):
                x["href"] = link_of(it)
            ic = (it.get("selected_icon") or {}).get("value")
            if isinstance(ic, dict) and "telefon" in (ic.get("url") or ""):
                x["icon"] = "phone"
            items.append(x)
        if items:
            out.append({"t": "list", "items": items})
    elif w == "shortcode":
        sc = st.get("shortcode") or ""
        if "trustindex" in sc:
            out.append({"t": "ressenyes"})
        elif "gtranslate" in sc:
            pass
        elif sc.strip():
            out.append({"t": "text", "html": html.escape(sc)})
    elif w in ("anwp-pg-simple-slider", "posts"):
        if w == "posts":    # /articulos/: 9 per pàgina, amb paginació (/articulos/page/2/ ...) i un resum de 13 paraules
            b = {"t": "articles", "n": int(st.get("classic_posts_per_page") or 9), "paginated": True,
                 "excerpt": int(st.get("classic_excerpt_length") or 25)}
        else:               # portada: els últims articles
            b = {"t": "articles", "n": 3}
        out.append(b)
    elif w == "form":
        out.append({"t": "contacte"})          # decisió 5: sense formulari; botons de telèfon, WhatsApp i correu
    elif w == "google_maps":
        out.append({"t": "mapa"})
    elif w == "spacer":
        pass
    else:
        out.append({"t": "text", "html": f"<!-- [PENDENT] giny d'Elementor {w} -->"})


def has_bg(st):
    return st.get("background_background") in ("classic", "gradient") and (
        st.get("background_color") or (st.get("background_image") or {}).get("url") or st.get("background_color_b"))


def is_dark(color):
    m = re.match(r"#?([0-9a-f]{6})", (color or "").strip(), re.I)
    if not m:
        return False
    r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) < 140


def conv_column(col, media):
    """Una columna → llista de blocs. Les seccions de dins amb més d'una columna amb contingut fan una fila pròpia."""
    blocks = []
    for e in col.get("elements") or []:
        if e.get("elType") == "widget":
            conv_widget(e, media, blocks)
        elif e.get("elType") == "section":
            if hidden_desktop(e.get("settings") or {}):
                continue
            cols = [conv_column(c, media) for c in e.get("elements") or []]
            cols = [c for c in cols if c]
            if not cols:
                continue
            panel = panel_tone(e.get("settings") or {})
            if len(cols) == 1 or all(all(b["t"] == "btn" for b in c) for c in cols):
                inner = [b for c in cols for b in c]
            else:
                inner = [{"t": "row", "cols": cols}]
            if panel:
                blocks.append({"t": "panel", "tone": panel, "blocks": inner})
            else:
                blocks.extend(inner)
    tone = panel_tone(col.get("settings") or {})
    if tone and blocks:
        return [{"t": "panel", "tone": tone, "blocks": blocks}]
    return blocks


def panel_tone(st):
    """Un requadre amb color de fons a la web d'ara: «white» (blanc), «light» (clar) o «dark» (fosc).
    Els colors d'ara (marró i blau) passen als blaus del logo (decisió 14)."""
    if st.get("background_background") != "classic" or (st.get("background_image") or {}).get("url"):
        return None
    c = (st.get("background_color") or "").lower()
    if not c:
        return "light" if (st.get("__globals__") or {}).get("background_color") else None
    if c.startswith("#ffffff") or c in ("#fff",):
        return "white"
    return "dark" if is_dark(c) else "light"


def unwrap(blocks, tone=None):
    """Un requadre dins d'un altre del mateix color no es dibuixa dues vegades."""
    out = []
    for b in blocks:
        if b["t"] == "panel":
            b["blocks"] = unwrap(b["blocks"], b["tone"])
            if b["tone"] == tone:
                out.extend(b["blocks"])
                continue
        elif b["t"] == "row":
            b["cols"] = [unwrap(c, tone) for c in b["cols"]]
        out.append(b)
    return out


def conv_sections(data, media):
    out = []
    for sec in data:
        st = sec.get("settings") or {}
        if hidden_desktop(st):
            continue
        cols = [unwrap(conv_column(c, media)) for c in sec.get("elements") or []]
        cols = [c for c in cols if c]
        if not cols:
            continue
        s = {"cols": cols}
        bg = upload_path((st.get("background_image") or {}).get("url")) if st.get("background_background") == "classic" else None
        if bg:
            s["bg"] = bg
        tone = panel_tone(st)
        if tone:
            s["tone"] = tone
        out.append(s)
    # Una secció que només té un títol fa de capçalera de la següent (com ara: «Psicólogos especialistas en:» + targetes)
    merged = []
    for s in out:
        if merged:
            prev = merged[-1]
            only_heads = len(prev["cols"]) == 1 and all(b["t"] == "h" for b in prev["cols"][0]) and len(prev["cols"][0]) <= 2
            if only_heads and not prev.get("bg") and not s.get("bg") and "head" not in prev:
                s = dict(s, head=prev["cols"][0])
                merged[-1] = s
                continue
        merged.append(s)
    return merged


# ---------------------------------------------------------------- pàgines i entrades

LANG = {"castellà": "es", "català": "ca"}


def seo_fields(url, inv, seo):
    r = inv.get(norm_url(url))
    s = seo.get(norm_url(url))
    out = {}
    if r:
        out["seo_title"] = r[2] or ""
        out["description"] = r[3] or ""
        out["lang"] = LANG.get((r[4] or "").strip(), "es")
        if r[16]:
            out["keyword"] = r[16]
    if s:
        if s[3]:
            out["h1_inventari"] = s[3]
        if s[8]:
            out["og_title"] = s[8]
        if s[9]:
            out["og_image"] = local_url(s[9])
    return out


def correccions(path, p):
    """Canvis de presentació decidits a la fase 3 (el text no es toca):
    - /contacto-3/: fora les dues imatges que emmarcaven el formulari (decisió 5: ja no hi ha formulari)."""
    def drop(bl, names):
        out = []
        for b in bl:
            if b["t"] == "img" and b["src"] in names:
                continue
            if b["t"] == "panel":
                b["blocks"] = drop(b["blocks"], names)
            if b["t"] == "row":
                b["cols"] = [drop(c, names) for c in b["cols"]]
            out.append(b)
        return out
    if path == "contacto-3":
        for s in p.get("sections", []):
            s["cols"] = [drop(c, {"2023/05/Vector-1.png", "2023/05/Vector-2.png"}) for c in s["cols"]]


def iso(d):
    return (d or "")[:10]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = None
    if "--nomes" in sys.argv:
        only = set(sys.argv[sys.argv.index("--nomes") + 1].split(","))
    xml_path, inv_path = args[0], args[1]
    items = load_xml(xml_path)
    inv, seo = load_inventory(inv_path)
    media = build_media(items)
    by_id = {i["id"]: i for i in items}
    (DATA / "pages").mkdir(parents=True, exist_ok=True)
    (DATA / "articles").mkdir(parents=True, exist_ok=True)
    (DATA / "media.json").write_text(json.dumps(media, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")

    n_pages = n_posts = 0
    for it in items:
        if it["status"] != "publish" or it["type"] not in ("page", "post"):
            continue
        path = unquote(it["link"].replace(SITE, "")).strip("/")
        if only is not None and path not in only:
            continue
        p = {"path": path, "wp_id": it["id"], "title": html.unescape(it["title"]),
             "published": iso(it["date"]), "modified": iso(it["modified"])}
        p.update(seo_fields(it["link"], inv, seo))
        if it["meta"].get("rank_math_canonical_url"):
            p["canonical_wp"] = it["meta"]["rank_math_canonical_url"]
        thumb = it["meta"].get("_thumbnail_id")
        if thumb and int(thumb) in by_id:
            p["image"] = upload_path(by_id[int(thumb)]["url"])
        if it["type"] == "page":
            el = it["meta"].get("_elementor_data")
            if el and it["meta"].get("_elementor_edit_mode") == "builder":
                p["sections"] = conv_sections(json.loads(el), media)
                correccions(path, p)
            elif it["content"].strip():
                p["html"] = clean_post_html(it["content"])
            else:
                p["html"] = "<p>[PENDENT] Aquesta pàgina la generava un plugin (Adapta RGPD) i el seu text no és a l'exportació.</p>"
            dest = DATA / "pages" / ((path or "index") + ".json")
            n_pages += 1
        else:
            p["html"] = clean_post_html(it["content"])
            p["categories"] = [c[1] for c in it["cats"] if c[0] == "category"]
            p["tags"] = [c[1] for c in it["cats"] if c[0] == "post_tag"]
            dest = DATA / "articles" / (path + ".json")
            n_posts += 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Importades {n_pages} pàgines i {n_posts} entrades; {len(media)} fitxers a la biblioteca.")


if __name__ == "__main__":
    main()
