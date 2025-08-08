# =====================================================
# 🚀 Structured Data Analyser — compact UI (stateful, robots override)
# =====================================================
import streamlit as st
import extruct
from w3lib.html import get_base_url
import pandas as pd
import json
import datetime
import time
import random
import requests
from urllib.parse import urlparse
import urllib.robotparser as robotparser

# ---------------------------
# Page / thème / CSS compact
# ---------------------------
st.set_page_config(page_title="🚀 Structured Data Analyser", layout="wide")

COMPACT_CSS = """
<style>
.block-container {padding-top: 1.0rem; padding-bottom: 0.8rem;}
h1, h2, h3, h4 { margin: 0.2rem 0 0.6rem 0; }
.stTextInput, .stTextArea, .stNumberInput { margin-bottom: 0.4rem; }
div[data-baseweb="input"] input, textarea { font-size: 0.95rem; }
/* tableaux plus denses */
td, th { vertical-align: middle !important; }
</style>
"""
st.markdown(COMPACT_CSS, unsafe_allow_html=True)
st.markdown("## 🚀 Structured Data Analyser")

# ------------------------
# 🌐 Récup HTML (robots.txt optionnel) + headers “navigateur”
# ------------------------
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

def is_allowed_by_robots(url: str, user_agent: str = DEFAULT_UA) -> bool:
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True  # si illisible, on suppose OK

def build_headers(url, ua=DEFAULT_UA):
    origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": origin,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "sec-ch-ua": '"Chromium";v="123", "Not:A-Brand";v="8"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

def smart_get(session: requests.Session, url: str, timeout: int = 15) -> requests.Response:
    """Variante “propre” pour limiter les 403 (slash/AMP + petits retries)."""
    tried = set()
    variants = [url]
    if not url.endswith("/"):
        variants.append(url + "/")
    if "?" in url:
        variants.append(url + "&amp=1")
    else:
        variants.append(url + "?amp=1")
    if not url.rstrip("/").endswith("/amp"):
        variants.append(url.rstrip("/") + "/amp")

    last_exc = None
    for u in variants:
        if u in tried: 
            continue
        tried.add(u)
        headers = build_headers(u)
        try:
            resp = session.get(u, headers=headers, allow_redirects=True, timeout=timeout)
            ctype = (resp.headers.get("content-type") or "").lower()
            if 200 <= resp.status_code < 300 and ("text/html" in ctype or "application/xhtml+xml" in ctype):
                return resp
            if resp.status_code in (403, 406, 451):
                time.sleep(0.4 + random.random() * 0.6)
                continue
        except Exception as e:
            last_exc = e
            time.sleep(0.2)
            continue
    if last_exc:
        raise last_exc
    raise requests.HTTPError(f"Échec de récupération (403/variants) pour {url}")

@st.cache_data(show_spinner=False, ttl=900)
def fetch_html(url: str, respect_robots: bool = True, timeout: int = 15) -> str:
    """Télécharge l’HTML. Si respect_robots=False, on ne bloque pas sur robots.txt (tu assumes l’usage)."""
    if not url:
        return ""
    if respect_robots and not is_allowed_by_robots(url):
        raise PermissionError(f"L’accès à {url} est refusé par robots.txt (désactive l’option pour ignorer).")
    with requests.Session() as s:
        s.headers.update(build_headers(url))
        resp = smart_get(s, url, timeout=timeout)
        resp.raise_for_status()
        return resp.text or ""

# ------------------------
# 🔎 Extraction JSON-LD + flatten (cachée)
# ------------------------
def extract_jsonld_schema(html_content: str, url: str = "http://example.com"):
    base_url = get_base_url(html_content, url)
    data = extruct.extract(html_content, base_url=base_url, syntaxes=["json-ld"], uniform=True)
    return data.get("json-ld", [])

def flatten_schema(jsonld_data):
    """Retourne set[(Type, Propriété)]"""
    results = set()
    def recurse(obj, current_type=None):
        if isinstance(obj, dict):
            obj_type = obj.get('@type', current_type)
            if obj_type:
                results.add((obj_type, '@type'))
            for k, v in obj.items():
                if k != '@type':
                    results.add((obj_type or "Unknown", k))
                    recurse(v, obj_type)
        elif isinstance(obj, list):
            for it in obj:
                recurse(it, current_type)
    recurse(jsonld_data)
    return results

@st.cache_data(show_spinner=False, ttl=900)
def build_pairs_from_html(html: str, url: str):
    data = extract_jsonld_schema(html, url=url)
    pairs = set()
    for block in data:
        pairs |= flatten_schema(block)
    return pairs

def colorize(val):
    if val == "✅": return "color: green"
    if val == "❌": return "color: red"
    return ""

# ------------------------
# 🧩 Layout : gauche (inputs) | droite (résultats)
# ------------------------
left, right = st.columns([5, 7])

# État UI
if "competitor_count" not in st.session_state:
    st.session_state.competitor_count = 1
if "results" not in st.session_state:
    st.session_state.results = None  # (df, missing, competitor_names)
if "active_type" not in st.session_state:
    st.session_state.active_type = None

with left:
    st.markdown("### 🟢 Votre page")
    client_url = st.text_input("URL de la page (votre site)", placeholder="https://…")
    client_html = st.text_area("OU collez l’HTML (prioritaire si rempli)", height=120)

    st.markdown("### 🔴 Concurrents")
    st.session_state.competitor_count = st.number_input(
        "Nombre de concurrents", min_value=1, max_value=5, value=st.session_state.competitor_count, step=1
    )

    competitor_entries = []
    for i in range(int(st.session_state.competitor_count)):
        st.markdown(f"**Concurrent {i+1}**")
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(f"Nom {i+1}", key=f"name_{i}", value=f"Concurrent {i+1}")
            url = st.text_input(f"URL {i+1}", key=f"url_{i}", placeholder="https://…")
        with c2:
            html = st.text_area(f"HTML {i+1}", key=f"html_{i}", height=90)
        competitor_entries.append((name, url, html))

    respect_robots = st.checkbox(
        "Respecter robots.txt (recommandé)", value=True,
        help="Si décoché, l’outil ne bloque pas sur robots.txt. Utile pour les sites très restrictifs. À utiliser si tu as le droit."
    )

    run = st.button("🔍 Lancer l’analyse")

# ------------------------
# ⚙️ Analyse (une seule fois) + persistance
# ------------------------
def analyze_once(client_url, client_html, competitor_entries, respect_robots=True):
    # Client
    if client_html.strip():
        client_html_final = client_html
        client_eff_url = client_url or "http://example.com"
    elif client_url.strip():
        client_html_final = fetch_html(client_url, respect_robots=respect_robots)
        client_eff_url = client_url
    else:
        st.error("Merci de fournir au moins l’URL ou l’HTML de votre page.")
        st.stop()

    client_pairs = build_pairs_from_html(client_html_final, client_eff_url)

    # Concurrents
    competitor_names = []
    competitor_pairs_list = []
    all_keys = set(client_pairs)

    for i, (name, url, html) in enumerate(competitor_entries):
        comp_name = name or f"Concurrent {i+1}"
        competitor_names.append(comp_name)
        try:
            if html.strip():
                comp_html = html
                comp_eff_url = url or "http://example.com"
            elif url.strip():
                comp_html = fetch_html(url, respect_robots=respect_robots)
                comp_eff_url = url
            else:
                st.warning(f"[{comp_name}] Pas d’URL ni HTML — ignoré.")
                competitor_pairs_list.append(set())
                continue
            pairs = build_pairs_from_html(comp_html, comp_eff_url)
        except PermissionError as e:
            st.warning(f"[{comp_name}] {e}")
            pairs = set()
        except Exception as e:
            st.warning(f"[{comp_name}] Récupération impossible : {e}")
            pairs = set()

        competitor_pairs_list.append(pairs)
        all_keys |= pairs

    # Table
    rows = []
    missing = []
    for item_type, prop in sorted(all_keys):
        row = {
            "Type": item_type,
            "Propriété": prop,
            "Votre site": "✅" if (item_type, prop) in client_pairs else "❌"
        }
        at_least_one = False
        for i, pairs in enumerate(competitor_pairs_list):
            has_it = "✅" if (item_type, prop) in pairs else "❌"
            if has_it == "✅": at_least_one = True
            name = competitor_names[i]
            if name in row:  # collision éventuelle
                name = f"{name} ({i+1})"
            row[name] = has_it
        if row["Votre site"] == "❌" and at_least_one:
            missing.append((item_type, prop))
        rows.append(row)

    df = pd.DataFrame(rows)
    return df, missing, competitor_names

if run:
    try:
        st.session_state.results = analyze_once(client_url, client_html, competitor_entries, respect_robots=respect_robots)
        # reset du filtre de type à chaque nouvelle analyse
        st.session_state.active_type = None
    except Exception as e:
        st.session_state.results = None
        st.error(f"Erreur d’analyse : {e}")

# ------------------------
# 🧾 Résultats (droite) — interactifs sans reset
# ------------------------
with right:
    st.markdown("### 📈 Résultats")
    if not st.session_state.results:
        st.info("⚡ Renseigne les URLs/HTML à gauche puis clique **Lancer l’analyse**.")
    else:
        df, missing_opportunities, competitor_names = st.session_state.results

        if df.empty or "Type" not in df.columns:
            st.info("Aucune donnée JSON-LD détectée. Essaie une page produit ou colle le HTML.")
            st.stop()

        # Filtre “uniquement manquants”
        show_only_missing = st.toggle("Afficher uniquement les propriétés manquantes sur votre site", value=False)
        view_df = df[df["Votre site"].eq("❌")].copy() if show_only_missing else df.copy()

        # Sélecteur “Type détecté” — pas de bouton, pas de reset
        types = list(view_df["Type"].dropna().unique())
        sel_col1,_
