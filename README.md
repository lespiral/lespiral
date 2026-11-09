# Web de L'Espiral (lespiral.cat)

Web estàtica de L'Espiral, el centre de psicoteràpia del Prat de Llobregat. Substitueix el WordPress de Bluehost
**sense canviar cap adreça**, amb el mateix sistema que espiralosona.com i elarasocial.com (repositoris
`lespiral/espiralosona` i `lespiral/elarasocial`): dades en JSON, plantilles i un sol full d'estils.
Es publica amb GitHub Pages des de la carpeta `docs/` de la branca `main`.

Estat (9/11/2026, fase 4 tancada): web sencera i comprovada a l'adreça de proves (226 pàgines, 35 adreces antigues
redirigides), amb les ressenyes (decisió 7) i els textos de galetes (decisió 8) aprovats per l'Aleix. Cap marca
`[PENDENT]`. Les decisions (D1–D21) són al pla de treball del projecte de Claude i a l'inventari. Següent pas: el canvi
de DNS (fase 5), només amb l'OK de l'Aleix.

## On és cada cosa

- `data/site.json`: nom, adreça pública (`publish`), menú (`nav`), botó «Pide una cita» (`cta`), contacte,
  punt del mapa (`geo`, el de la fitxa de Google, decisió 13), dades per a Google (`organization`), ressenyes
  (`reviews`, decisió 7), peu (`footer`), arxius de la categoria i les etiquetes (`archives`) i adreces antigues (`redirects`).
- `data/pages/<adreça>.json`: les 50 pàgines. `data/pages/psicoterapias/psicoterapia-adultos.json` es publica a
  `/psicoterapias/psicoterapia-adultos/`; la portada és `data/pages/index.json`.
- `data/articles/<adreça>.json`: les 143 entrades (articles), amb el seu HTML.
- `data/media.json`: la biblioteca de mitjans del WordPress (mides i text alternatiu de cada imatge).
- `data/legal/`: l'Avís legal i la Política de privacitat tal com els va reproduir la importació (els feia el plugin
  Adapta RGPD i no eren a l'exportació; comprovats paraula per paraula amb la web d'ara). El text que es publica és
  el de `data/pages/aviso-legal.json` i `data/pages/politica-de-privacidad.json`: un canvi s'hi ha de fer allà (i,
  per tenir-ho igual, també aquí). Des del 9/11/2026 la Política de privacitat té el paràgraf de galetes adaptat a la
  web nova (OK de l'Aleix). Aquestes pàgines i les de galetes porten `noindex, follow`, com abans.
- `static/`: es copia tal qual. `static/wp-content/uploads/` són les imatges i els PDF **originals** a la mateixa
  ruta que al WordPress (decisió 19; no s'han de recomprimir: 121 porten coordenades GPS); `google8d37b0a77b34efe5.html`
  i `googlebb28148fcce2edc7.html` (verificació de Search Console, decisió 12) i `llms.txt`.
- `src/templates/`: les plantilles. `parts.html` pinta les seccions que venen d'Elementor.
- `src/site.css` i `src/site.js`: l'aspecte (el d'Osona: Playfair Display + Inter i els blaus del logo, decisió 14).
- `tools/importa-wordpress.py`: la importació del WordPress (es va fer una vegada; vegeu més avall).
- `docs/`: la web generada. No s'edita a mà.

## Com es fa un canvi

1. Canvia el text al fitxer de `data/`.
2. Genera la web: `python3 build.py`. Diu quantes marques `[PENDENT]` queden i quins enllaços interns no porten enlloc.
3. Prova-la: `python3 tools/proves.py` (mòbil i ordinador: errors, scroll lateral, imatges i enllaços) i
   `python3 tools/comprova.py inventari.xlsx` (cada adreça de l'inventari, títols, descripcions, H1 i H2).
4. Desa i puja els canvis. GitHub Pages la publica sola.

No s'han d'inventar dades: el que falta es deixa marcat amb `[PENDENT]`.

## Una pàgina

Les pàgines fetes amb Elementor es guarden com a seccions → columnes → blocs, amb el text i les etiquetes d'ara:

```json
{"path": "psicoterapias/psicoterapia-adultos", "seo_title": "…", "description": "…", "lang": "es",
 "published": "2023-05-24", "modified": "2026-10-21", "keyword": "…",
 "sections": [{"bg": "2023/06/foto.jpg", "cols": [[{"t": "h", "tag": "h1", "html": "PSICOTERAPIA ADULTOS"}, {"t": "btn", "text": "Pide una cita", "href": "/contacto-3/"}]]}]}
```

Blocs: `h` (encapçalament; `tag` és h1–h6 o p), `text` (HTML), `img` (`src` és el camí dins de wp-content/uploads,
`alt`), `btn`, `list`, `panel` (requadre: `white`, `light` o `dark`), `row` (columnes dins d'una columna),
`ressenyes`, `articles`, `contacte` (telèfon, WhatsApp i correu, decisió 5) i `mapa`.
Una franja amb `bg` té la foto de fons; la primera, si té foto o l'H1, és la capçalera.
El títol i la descripció per a Google (`seo_title`, `description`) són els que mostrava el WordPress (inventari).

## SEO que es manté

- Mateixes adreces, amb la barra final. Canònic a `https://lespiral.cat/…`.
- Títol, descripció, H1, H2, textos i text alternatiu de les imatges, com ara.
- Dades estructurades com les de Rank Math (Organization, Place, WebSite, WebPage, Person, Article/BlogPosting),
  amb l'adreça i el punt de la fitxa de Google, i les etiquetes geo (decisió 13).
- Mapes del web amb els mateixos noms: `sitemap_index.xml`, `post-sitemap.xml`, `page-sitemap.xml`.
- `robots.txt`: en proves no hi entra ningú. Amb el domini hi entren els cercadors i les IA (decisió 21), i es
  bloquegen les mateixes eines de SEO, robots agressius i cercadors estrangers que bloquejava el WordPress.
- Feeds: `/feed/` i `/category/articulos/feed/` (decisió 20).
- Arxius i paginacions: `/category/articulos/` (10 per pàgina), `/tag/gestaltmindfulness/` i `/articulos/page/N/` (9 per pàgina) (decisió 9).
- Adreces antigues (22 del 2023 i 7 variants mal escrites): porten a la bona a l'instant (meta refresh i canònic;
  GitHub Pages no fa redireccions 301) (decisions 10 i 11). Les adreces que no existeixen porten a `404.html`.
- Sense Tag Manager, sense avís de galetes, sense GTranslate ni Trustindex (decisions 1, 7 i 8). El mapa de Google
  només es carrega quan es clica. Els 3 vídeos de YouTube dels articles són un enllaç que els obre a YouTube (el canal
  no deixa inserir-los; l'Aleix ho revisarà quan els passi a un altre canal).

## Publicació

- GitHub Pages, branca `main`, carpeta `/docs`.
- L'adreça i si surt als cercadors són a `data/site.json`, a `publish`. Ara: `https://lespiral.github.io/lespiral/`
  i `"index": false` (proves, amb noindex).
- El dia del canvi de domini (fase 5, només amb l'OK de l'Aleix): fitxer `CNAME` amb `lespiral.cat`,
  `publish` a `https://lespiral.cat/` i `"index": true`, i als DNS de Bluehost només el registre A de l'arrel
  (les 4 IP de GitHub Pages) i el CNAME `www` → `lespiral.github.io`. El correu i els subdominis no es toquen.

## Importació del WordPress (una vegada)

`python3 tools/importa-wordpress.py exportacio.xml inventari.xlsx` llegeix l'exportació del WordPress (còpia de
seguretat del 8/11/2026) i el full «Inventari d'adreces de lespiral.cat» (descarregat en Excel) i escriu `data/`.
Cap dels dos fitxers es desa al repositori. Si es torna a fer, es perden els canvis fets a mà a `data/`.
