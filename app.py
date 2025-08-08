# app.py
# =========================================================
# 🚀 Structured Data Analyser — URLs, concurrents + catégories
# =========================================================
import os
import re
import time
import json
import datetime
import random
import asyncio
from urllib.parse import urlparse, urljoin, urlunparse

import streamlit as st
import pandas as pd
import httpx
import requests
from httpx import Timeout
from bs4 import BeautifulSoup
import extruct
from w3lib.html import get_base_url
from urllib import robotparser

# ------------------------
# Config UI
# ------------------------
st.set_page_config(page_title="🚀 Structured Data Analyser", layout="wide")
st.title("🚀 Structured Data Analyser")

# ------------------------
# Sidebar: réseau + crawl
# ------------------------
with st.sidebar:
    st.header("⚙️ Réseau")
    TIMEOUT_S = st.slider("Timeout (secondes)", 5, 60, 30, 1)
    RETRIES = st.slider("Retries", 0, 5, 2, 1)

    st.header("🕷️ Crawl catégories")
    CRAWL_CATEGORIES = st.checkbox("Explorer les catégories (poliment)", value=False)
    MAX_CATEGORIES = st.number_input("Nb max de catégories", 1, 50, 8, 1)
    MAX_PAGES_PER_CATEGORY = st.number_input("Pages produit par catégorie (échantillon)", 1, 30, 3, 1)
    CONCURRENCY = st.slider("Concurrence (requêtes simultanées)", 1, 10, 4, 1)
    DELAY_S = st.slider("Délai entre requêtes (s)", 0.0, 3.0, 0.6, 0.1)

    st.caption("Astuce : privilégie des **pages produit** pour l'extraction directe. "
               "Le crawl catégories essaie de rester léger et respectueux.")

# ------------------------
# Téléchargement robuste
# ------------------------
DESKTOP_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

def _base_headers(ua: str):
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }

def looks_like_waf(html: str) -> bool:
    low = (html or "").lower()
    needles = ("captcha", "access denied", "are you a robot", "bot detection", "cloudflare", "automated access")
    return any(n in low for n in needles)

@st.cache_data(show_spinner=False, ttl=60*60)
def fetch_url_html(url: str, timeout_s: int = 30, retries: int = 2) -> str:
    """HTTP/1.1 + cookies + referer + retries ; fallback requests."""
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url

    last_err = None
    for attempt in range(retries + 1):
        ua = random.choice(DESKTOP_UAS)
        headers = _base_headers(ua)
        try:
            t = Timeout(connect=10.0, read=timeout_s, write=20.0, pool=5.0)
            p = urlparse(url)
            origin = urlunparse((p.scheme, p.netloc, "/", "", "", ""))

            # Try with httpx (keeps cookies)
            with httpx.Client(follow_redirects=True, timeout=t, headers=headers) as client:
                # seed cookies
                try:
                    client.get(origin)
                except Exception:
                    pass

                # main request with Referer
                hdrs = dict(headers)
                hdrs["Referer"] = origin
                resp = client.get(url, headers=hdrs)
                if resp.status_code == 403:
                    # one more try with another UA
                    hdrs2 = _base_headers(random.choice(DESKTOP_UAS))
                    hdrs2["Referer"] = origin
                    resp = client.get(url, headers=hdrs2)

                resp.raise_for_status()
                html = resp.text
                if looks_like_waf(html):
                    raise RuntimeError("Page protégée (anti-bot)")
                return html

        except Exception as e:
            last_err = e
            time.sleep(1.2 * (attempt + 1))

    # Fallback with requests
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=_base_headers(random.choice(DESKTOP_UAS)),
                             allow_redirects=True, timeout=(10, timeout_s))
            r.raise_for_status()
            html = r.text
            if looks_like_waf(html):
                raise RuntimeError("Page protégée (anti-bot)")
            return html
        except Exception as e:
            last_err = e
            time.sleep(1.2 * (attempt + 1))

    raise last_err

# ------------------------
# Extraction JSON-LD
# ------------------------
def extract_jsonld_schema(html_content, url="http://example.com"):
    base_url = get_base_url(html_content, url)
    data = extruct.extract(
        html_content,
        base_url=base_url,
        syntaxes=['json-ld'],
        uniform=True
    )
    return data.get('json-ld', [])

def flatten_schema(jsonld_data):
    results = set()
    def recurse(obj, current_type=None):
        if isinstance(obj, dict):
            obj_type = obj.get('@type', current_type)
            if obj_type:
                results.add((obj_type, '@type'))
            for key, value in obj.items():
                if key != '@type':
                    results.add((obj_type, key))
                    recurse(value, obj_type)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item, current_type)
    recurse(jsonld_data)
    return results

def extract_from_input(html_or_url: str, mode: str, timeout_s: int, retries: int):
    """mode: 'url' ou 'html' → (set((type, prop)), html)."""
    if mode == "url":
        html = fetch_url_html(html_or_url, timeout_s=timeout_s, retries=retries)
        base_url = html_or_url
    else:
        html = html_or_url
        base_url = "http://example.com"

    data = extract_jsonld_schema(html, url=base_url)
    schema = set()
    for block in data:
        schema |= flatten_schema(block)
    return schema, html

# ------------------------
# Catégories — découverte & crawl
# ------------------------
CATEGORY_PATTERNS = re.compile(r"(cat|categ|category|/c/|/categories|/rayon|/depart|/f/|/s\?)", re.I)
PRODUCT_PATTERNS = re.compile(r"(/product|/p/|/dp/|/gp/product|/produit|/article|/sku)", re.I)

def same_host(u1: str, u2: str) -> bool:
    return urlparse(u1).netloc == urlparse(u2).netloc

def is_category_url(url: str) -> bool:
    u = url.lower()
    return bool(CATEGORY_PATTERNS.search(u)) and not PRODUCT_PATTERNS.search(u)

def is_allowed_by_robots(base_url: str, path: str) -> bool:
    rp = robotparser.RobotFileParser()
    origin = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    rp.set_url(urljoin(origin, "/robots.txt"))
    try:
        rp.read()
    except Exception:
        return True
    return rp.can_fetch("*", urljoin(origin, path))

def discover_categories_from_sitemap(origin: str, timeout=15) -> list:
    client = httpx.Client(timeout=timeout, follow_redirects=True)
    urls_to_try = [urljoin(origin, "/sitemap.xml"), urljoin(origin, "/sitemap_index.xml")]
    found = set()
    try:
        for sm in urls_to_try:
            try:
                r = client.get(sm)
                if r.status_code >= 400:
                    continue
                soup = BeautifulSoup(r.text, "xml")
                for loc in soup.find_all("loc"):
                    href = loc.get_text(strip=True)
                    if same_host(origin, href) and is_category_url(href):
                        found.add(href)
            except Exception:
                continue
    finally:
        client.close()
    return list(found)

def discover_categories_from_home(origin: str, timeout=15) -> list:
    client = httpx.Client(timeout=timeout, follow_redirects=True)
    cats = set()
    try:
        r = client.get(origin)
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select("a[href]"):
            href = urljoin(origin, a["href"])
            if same_host(origin, href) and is_category_url(href):
                cats.add(href.split("#")[0])
    except Exception:
        pass
    finally:
        client.close()
    return list(cats)

async def _afetch(client: httpx.AsyncClient, url: str, sem: asyncio.Semaphore, delay: float):
    async with sem:
        try:
            resp = await client.get(url)
            await asyncio.sleep(delay)
            resp.raise_for_status()
            return url, resp.text, None
        except Exception as e:
            return url, "", e

async def async_fetch_many(urls: list, timeout_s: int, concurrency: int, delay_s: float, base_headers: dict):
    results = []
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=Timeout(connect=10, read=timeout_s, write=20, pool=5),
        headers=base_headers
    ) as client:
        tasks = [_afetch(client, u, sem, delay_s) for u in urls]
        for fut in asyncio.as_completed(tasks):
            results.append(await fut)
    return results

def pick_sample_pages_from_category(cat_url: str, html: str, max_pages: int = 3) -> list:
    soup = BeautifulSoup(html, "lxml")
    items = []
    for a in soup.select("a[href]"):
        href = urljoin(cat_url, a["href"])
        if same_host(cat_url, href) and PRODUCT_PATTERNS.search(href):
            items.append(href.split("#")[0])
        if len(items) >= max_pages:
            break
    # dédupe en gardant l'ordre
    return list(dict.fromkeys(items))

def analyse_categories(base_url: str, timeout_s: int, retries: int, max_categories: int,
                       pages_per_cat: int, concurrency: int, delay_s: float):
    origin = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    # 1) découvre catégories
    cats = discover_categories_from_sitemap(origin)
    if not cats:
        cats = discover_categories_from_home(origin)

    # filtre robots.txt + limite
    filtered = []
    for u in cats:
        path = urlparse(u).path or "/"
        if is_allowed_by_robots(origin, path):
            filtered.append(u)
        if len(filtered) >= max_categories:
            break

    if not filtered:
        return [], {}

    # 2) fetch HTML des catégories (async → séquentiel fallback)
    base_headers = _base_headers(random.choice(DESKTOP_UAS))
    try:
        results = asyncio.run(async_fetch_many(filtered, timeout_s, concurrency, delay_s, base_headers))
    except RuntimeError:
        results = []
        for u in filtered:
            try:
                html = fetch_url_html(u, timeout_s=timeout_s, retries=retries)
                results.append((u, html, None))
                time.sleep(delay_s)
            except Exception as e:
                results.append((u, "", e))

    cat_html_map = {u: html for u, html, err in results if not err and html}

    # 3) pour chaque catégorie, échantillonner quelques produits
    product_urls = []
    for u, html in cat_html_map.items():
        product_urls.extend(pick_sample_pages_from_category(u, html, max_pages=pages_per_cat))
    product_urls = list(dict.fromkeys(product_urls))  # dédupe

    # 4) fetch produits (async → fallback) puis extraction JSON-LD
    try:
        presults = asyncio.run(async_fetch_many(product_urls, timeout_s, concurrency, delay_s, base_headers))
    except RuntimeError:
        presults = []
        for u in product_urls:
            try:
                html = fetch_url_html(u, timeout_s=timeout_s, retries=retries)
                presults.append((u, html, None))
                time.sleep(delay_s)
            except Exception as e:
                presults.append((u, "", e))

    product_struct = {}
    for u, html, err in presults:
        if err or not html:
            continue
        blocks = extract_jsonld_schema(html, url=u)
        flat = set()
        for b in blocks:
            flat |= flatten_schema(b)
        product_struct[u] = flat

    return filtered, product_struct

# ------------------------
# Helpers UI
# ------------------------
def host_from_url(u: str) -> str:
    try:
        h = urlparse(u).netloc
        return h if h else u
    except Exception:
        return u

def guess_page_kind(url: str) -> str:
    u = (url or "").lower()
    if any(x in u for x in ["/category", "/categories", "/node=", "/s?k=", "/b?node="]):
        return "category"
    if any(x in u for x in ["/dp/", "/gp/product", "/product/", "/p/"]):
        return "product"
    return "generic"

# ------------------------
# ZONE DE SAISIE
# ------------------------
st.header("🟢 Votre site")
input_mode = st.radio("Mode d'entrée", ["URL (recommandé)", "Coller du HTML"], horizontal=True)

if input_mode == "URL (recommandé)":
    client_url = st.text_input("URL de votre site", placeholder="https://www.exemple.com/produit-xyz")
    if client_url and guess_page_kind(client_url) == "category":
        st.info("Conseil : les pages **catégorie** sont souvent protégées. "
                "Le **crawl catégories** peut échantillonner des produits automatiquement.")
    client_html = ""
    client_mode = "url"
else:
    client_html = st.text_area("Code HTML complet de votre site", height=250)
    client_url = ""
    client_mode = "html"

st.header("🔴 Concurrents")
competitor_count = st.number_input("Nombre de concurrents", min_value=1, max_value=5, value=1, step=1)

competitors = []
for i in range(competitor_count):
    with st.expander(f"Concurrent {i+1}", expanded=True):
        comp_mode = st.radio(
            f"Mode d'entrée - Concurrent {i+1}",
            ["URL", "HTML"],
            horizontal=True,
            key=f"mode_{i}"
        )
        if comp_mode == "URL":
            url = st.text_input(f"URL du concurrent {i+1}", key=f"url_{i}", placeholder="https://www.exemple.com/produit-abc")
            name_default = host_from_url(url) if url else f"Concurrent {i+1}"
            name = st.text_input(f"Nom affiché (optionnel) {i+1}", value=name_default, key=f"name_{i}")
            competitors.append({"name": name or f"Concurrent {i+1}", "mode": "url", "value": url})
        else:
            name = st.text_input(f"Nom du site Concurrent {i+1}", key=f"name_{i}", value=f"Concurrent {i+1}")
            html = st.text_area(f"Code HTML - {name}", key=f"competitor_{i}", height=200)
            competitors.append({"name": name, "mode": "html", "value": html})

# ------------------------
# COMPARAISON
# ------------------------
if st.button("🔍 Comparer les schémas"):
    # Validations
    if client_mode == "html" and not client_html.strip():
        st.error("Merci de fournir le code HTML de votre site **ou** une URL.")
        st.stop()
    if client_mode == "url" and not client_url.strip():
        st.error("Merci de fournir l'URL de votre site.")
        st.stop()

    st.header("📈 Résultat Comparatif")

    # Extraction client
    with st.spinner("Extraction des données structurées du site client..."):
        try:
            client_schema, _client_html_dbg = extract_from_input(
                client_url or client_html, client_mode, timeout_s=TIMEOUT_S, retries=RETRIES
            )
        except Exception as e:
            st.error(
                "Erreur lors de l'extraction du site client : "
                f"{e}. Astuces : augmente le timeout, réessaie, ou colle directement le HTML (fallback)."
            )
            st.stop()

    # (Option) Crawl catégories
    if CRAWL_CATEGORIES and client_mode == "url":
        with st.spinner("Exploration des catégories (polie)…"):
            try:
                cat_urls, cat_product_struct = analyse_categories(
                    client_url,
                    timeout_s=TIMEOUT_S,
                    retries=RETRIES,
                    max_categories=MAX_CATEGORIES,
                    pages_per_cat=MAX_PAGES_PER_CATEGORY,
                    concurrency=CONCURRENCY,
                    delay_s=DELAY_S,
                )
                if cat_urls:
                    st.success(f"{len(cat_urls)} catégories explorées • {sum(len(v) > 0 for v in cat_product_struct.values())} pages produit analysées")
                    with st.expander("Aperçu des catégories analysées"):
                        for u in cat_urls:
                            st.write("• ", u)
                    # fusionne les schémas produits trouvés dans le set client
                    for _u, flat_set in cat_product_struct.items():
                        client_schema |= flat_set
            except Exception as e:
                st.warning(f"Crawl catégories interrompu : {e}")

    # Extraction concurrents
    all_keys = set(client_schema)
    competitor_schemas = []
    competitor_names = []

    with st.spinner("Extraction des concurrents..."):
        for comp in competitors:
            name = comp["name"]
            competitor_names.append(name)
            value = comp["value"]
            mode = comp["mode"]
            if (mode == "url" and not value.strip()) or (mode == "html" and not value.strip()):
                competitor_schemas.append(set())
                continue
            try:
                comp_schema, _ = extract_from_input(value, "url" if mode == "url" else "html",
                                                    timeout_s=TIMEOUT_S, retries=RETRIES)
            except Exception as e:
                st.warning(f"{name} — erreur d'extraction : {e}")
                comp_schema = set()
            competitor_schemas.append(comp_schema)
            all_keys |= comp_schema

    # Construction du tableau
    rows = []
    missing_opportunities = []
    for item_type, prop in sorted(all_keys):
        row = {
            "Type": item_type,
            "Propriété": prop,
            "Votre site": "✅" if (item_type, prop) in client_schema else "❌"
        }

        at_least_one_has_it = False
        for i, schema in enumerate(competitor_schemas):
            has_it = "✅" if (item_type, prop) in schema else "❌"
            if has_it == "✅":
                at_least_one_has_it = True
            row[competitor_names[i]] = has_it

        if row["Votre site"] == "❌" and at_least_one_has_it:
            missing_opportunities.append((item_type, prop))

        rows.append(row)

    df = pd.DataFrame(rows)

    # Tableau comparatif par type
    st.subheader("🧩 Données comparées par type")
    grouped = df.groupby("Type", dropna=False)

    def colorize(val):
        return "color: green" if val == "✅" else "color: red"

    for group_type, group_df in grouped:
        with st.expander(f"📂 {group_type}", expanded=False):
            styled_group = group_df.style.applymap(colorize, subset=group_df.columns[2:])
            st.dataframe(styled_group, use_container_width=True)

    # Rapport opportunités
    with st.expander("📌 Rapport d'opportunités manquantes", expanded=True):
        st.markdown(f"**Nombre total d'opportunités manquantes sur votre site :** `{len(missing_opportunities)}`")
        if missing_opportunities:
            oppo_df = pd.DataFrame(missing_opportunities, columns=["Type", "Propriété"])
            st.dataframe(oppo_df, use_container_width=True)
        else:
            st.success("🎉 Votre site contient toutes les données structurées détectées chez les concurrents.")

    # Génération JSON-LD
    with st.expander("🛠️ Générer les données manquantes en JSON-LD", expanded=False):
        if missing_opportunities:
            schema_to_generate = {}
            for item_type, prop in missing_opportunities:
                if item_type not in schema_to_generate:
                    schema_to_generate[item_type] = {}
                if prop != '@type':
                    schema_to_generate[item_type][prop] = f"Exemple_{prop}"

            generated_jsonld = []
            for schema_type, props in schema_to_generate.items():
                block = {"@context": "https://schema.org", "@type": schema_type}
                block.update(props)
                generated_jsonld.append(block)

            editable_json = json.dumps(generated_jsonld, indent=2, ensure_ascii=False)
            user_json = st.text_area("✍️ JSON-LD généré automatiquement (modifiable)",
                                     value=editable_json, height=300)

            st.download_button(
                label="📥 Télécharger le JSON-LD",
                data=user_json,
                file_name=f"donnees-structurees-{datetime.date.today()}.json",
                mime="application/json"
            )
            st.markdown('👉 À intégrer dans une balise `<script type="application/ld+json">...</script>`.')
        else:
            st.info("Aucune donnée à générer. Votre site est complet sur les données analysées.")
