# =====================================================
# 🚀 Structured Data Analyser — fast streaming + AMP discovery + robots ignored
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
import re
from urllib.parse import urlparse, urljoin

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
td, th { vertical-align: middle !important; }
.smallnote {opacity:.8; font-size:.9rem}
</style>
"""
st.markdown(COMPACT_CSS, unsafe_allow_html=True)
st.markdown("## 🚀 Structured Data Analyser")

# ------------------------
# 🌐 Network helpers (robots.txt ignored; quick stream; AMP discovery)
# ------------------------
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

def build_headers(url, ua=DEFAULT_UA, cookie_str: str | None = None):
    origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": origin,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "sec-ch-ua": '"Chromium";v="124", "Not:A-Brand";v="8"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }
    if cookie_str:
        headers["Cookie"] = cookie_str
    return headers

def url_variants(url):
    v = [url]
    if not url.endswith("/"):
        v.append(url + "/")
    if "?" in url:
        v.append(url + "&amp=1")
    else:
        v.append(url + "?amp=1")
    if not url.rstrip("/").endswith("/amp"):
        v.append(url.rstrip("/") + "/amp")
    return v

# Regex for JSON-LD + AMP link
JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL
)
AMP_LINK_RE = re.compile(
    r'<link\s+rel=["\']amphtml["\']\s+href=["\']([^"\']+)["\']',
    re.IGNORECASE
)

def fast_extract_jsonld_blocks(html):
    blocks = []
    for m in JSONLD_RE.finditer(html or ""):
        raw = m.group(1).strip()
        raw = raw.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        try:
            data = json.loads(raw)
        except Exception:
            try:
                data = json.loads(f"[{raw}]")
            except Exception:
                continue
        if isinstance(data, list):
            blocks.extend(data)
        else:
            blocks.append(data)
    return blocks

def find_amp_link(html, base_url):
    m = AMP_LINK_RE.search(html or "")
    if not m:
        return None
    href = m.group(1).strip()
    return urljoin(base_url, href)

@st.cache_data(show_spinner=False, ttl=900)
def fetch_stream_first_meg(url: str, cookie_str: str | None, max_bytes: int = 2_000_000,
                           timeout_connect: int = 6, timeout_read: int = 6):
    """Return partial HTML (first ~2MB), JSON-LD blocks (if any), and AMP link (if any)."""
    with requests.Session() as s:
        s.headers.update(build_headers(url, cookie_str=cookie_str))
        r = s.get(url, stream=True, timeout=(timeout_connect, timeout_read), allow_redirects=True)
        r.raise_for_status()
        chunks = []
        size = 0
        for chunk in r.iterContent(chunk_size=32768) if hasattr(r, "iterContent") else r.iter_content(chunk_size=32768):
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size >= max_bytes:
                break
        html = b"".join(chunks).decode(r.apparent_encoding or "utf-8", errors="replace")
        blocks = fast_extract_jsonld_blocks(html)
        amp = find_amp_link(html, r.url)
        return html, blocks, amp

@st.cache_data(show_spinner=False, ttl=900)
def fetch_jsonld_with_variants_and_amp(url: str, cookie_str: str | None):
    """Try variants + quick partial read + AMP link if present."""
    last_exc = None
    for u in url_variants(url):
        try:
            html, blocks, amp = fetch_stream_first_meg(u, cookie_str=cookie_str)
            if blocks:
                return blocks
            if amp:
                # quick try AMP itself (partial stream)
                _, amp_blocks, _ = fetch_stream_first_meg(amp, cookie_str=cookie_str)
                if amp_blocks:
                    return amp_blocks
            time.sleep(0.2 + random.random() * 0.3)
        except Exception as e:
            last_exc = e
            time.sleep(0.2)
            continue
    if last_exc:
        raise last_exc
    return []

@st.cache_data(show_spinner=False, ttl=900)
def fetch_full_html(url: str, cookie_str: str | None, timeout_connect: int = 6, timeout_read: int = 25) -> str:
    with requests.Session() as s:
        s.headers.update(build_headers(url, cookie_str=cookie_str))
        r = s.get(url, timeout=(timeout_connect, timeout_read), allow_redirects=True)
        r.raise_for_status()
        return r.text

# ------------------------
# JSON-LD extraction helpers
# ------------------------
def extract_jsonld_schema(html_content: str, url: str = "http://example.com"):
    # Fast path first
    blocks = fast_extract_jsonld_blocks(html_content)
    if blocks:
        return blocks
    # Fallback to extruct
    try:
        base_url = get_base_url(html_content, url)
        data = extruct.extract(html_content, base_url=base_url, syntaxes=['json-ld'], uniform=True)
        return data.get('json-ld', [])
    except Exception:
        return []

def flatten_schema(jsonld_data):
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
def flatten_all(blocks):
    pairs = set()
    for block in blocks:
        pairs |= flatten_schema(block)
    return pairs

@st.cache_data(show_spinner=False, ttl=900)
def build_pairs_from_url(url: str, cookie_str: str | None):
    # 1) quick variants + AMP
    try:
        blocks = fetch_jsonld_with_variants_and_amp(url, cookie_str=cookie_str)
        if blocks:
            return flatten_all(blocks)
    except Exception:
        pass
    # 2) full HTML fallback
    html_full = fetch_full_html(url, cookie_str=cookie_str)
    blocks = extract_jsonld_schema(html_full, url=url)
    return flatten_all(blocks)

@st.cache_data(show_spinner=False, ttl=900)
def build_pairs_from_html(html: str, url: str):
    blocks = extract_jsonld_schema(html, url=url)
    return flatten_all(blocks)

def colorize(val):
    if val == "✅": return "color: green"
    if val == "❌": return "color: red"
    return ""

# ------------------------
# État Streamlit
# ------------------------
if "competitor_count" not in st.session_state:
    st.session_state.competitor_count = 1
if "results" not in st.session_state:
    st.session_state.results = None

# ------------------------
# UI gauche
# ------------------------
left, right = st.columns([5, 7])
with left:
    st.markdown("### 🟢 Votre page")
    client_url = st.text_input("URL de la page (votre site)", placeholder="https://…")
    client_html = st.text_area("OU collez l’HTML (prioritaire si rempli)", height=120)
    client_cookie = st.text_input("Cookie HTTP (optionnel, ex: consent=ok; geo=FR)", help="Si le site affiche un mur de consentement ou géo, colle ici les cookies autorisés.")

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
            cookie = st.text_input(f"Cookie {i+1} (optionnel)", key=f"cookie_{i}", help="Format: clé=val; clé2=val2")
        competitor_entries.append((name, url, html, cookie))

    run = st.button("🔍 Lancer l’analyse")

# ------------------------
# Analyse
# ------------------------
def analyze_once(client_url, client_html, client_cookie, competitor_entries):
    if client_html.strip():
        client_pairs = build_pairs_from_html(client_html, client_url or "http://example.com")
    elif client_url.strip():
        client_pairs = build_pairs_from_url(client_url, client_cookie or None)
    else:
        st.error("Merci de fournir au moins l’URL ou l’HTML de votre page.")
        st.stop()

    competitor_names = []
    competitor_pairs_list = []
    all_keys = set(client_pairs)

    for i, (name, url, html, cookie) in enumerate(competitor_entries):
        comp_name = name or f"Concurrent {i+1}"
        competitor_names.append(comp_name)
        try:
            if html.strip():
                pairs = build_pairs_from_html(html, url or "http://example.com")
            elif url.strip():
                pairs = build_pairs_from_url(url, cookie or None)
            else:
                st.warning(f"[{comp_name}] Pas d’URL ni HTML — ignoré.")
                competitor_pairs_list.append(set())
                continue
        except Exception as e:
            st.warning(f"[{comp_name}] Erreur : {e}")
            pairs = set()
        competitor_pairs_list.append(pairs)
        all_keys |= pairs

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
            row[competitor_names[i]] = has_it
        if row["Votre site"] == "❌" and at_least_one:
            missing.append((item_type, prop))
        rows.append(row)

    df = pd.DataFrame(rows)
    return df, missing, competitor_names

if run:
    try:
        st.session_state.results = analyze_once(client_url, client_html, client_cookie, competitor_entries)
    except Exception as e:
        st.session_state.results = None
        st.error(f"Erreur d’analyse : {e}")

# ------------------------
# Résultats à droite
# ------------------------
with right:
    st.markdown("### 📈 Résultats")
    if not st.session_state.results:
        st.info("⚡ Renseigne les URLs/HTML à gauche puis clique **Lancer l’analyse**.")
    else:
        df, missing_opportunities, competitor_names = st.session_state.results
        if df.empty or "Type" not in df.columns:
            st.info("Aucune donnée JSON-LD détectée (essaie une page produit, ou colle l’HTML).")
            st.stop()

        show_only_missing = st.toggle("Afficher uniquement les propriétés manquantes", value=False)
        view_df = df[df["Votre site"].eq("❌")].copy() if show_only_missing else df.copy()

        types = list(view_df["Type"].dropna().unique())
        sel_col1, sel_col2 = st.columns([3, 9])
        with sel_col1:
            selected_type = st.selectbox("Types détectés", options=["(Tous)"] + types, index=0)
        with sel_col2:
            if selected_type != "(Tous)":
                sub = view_df[view_df["Type"] == selected_type].copy()
                check_cols = [c for c in sub.columns if c not in ("Type", "Propriété")]
                styled = sub[["Propriété"] + check_cols].style.applymap(colorize, subset=check_cols)
                st.dataframe(styled, use_container_width=True)
            else:
                st.markdown("#### 🧩 Données comparées par type")
                for t, sub in view_df.groupby("Type", dropna=False):
                    with st.expander(f"📂 {t}", expanded=False):
                        check_cols = [c for c in sub.columns if c not in ("Type", "Propriété")]
                        styled = sub[["Propriété"] + check_cols].style.applymap(colorize, subset=check_cols)
                        st.dataframe(styled, use_container_width=True)

        st.markdown(f"**Total manquants :** `{len(missing_opportunities)}`")
        if missing_opportunities:
            opp_df = pd.DataFrame(sorted(missing_opportunities), columns=["Type", "Propriété"])
            if selected_type != "(Tous)":
                opp_df = opp_df[opp_df["Type"] == selected_type]
            st.dataframe(opp_df, use_container_width=True)
        else:
            st.success("🎉 Votre page contient toutes les données détectées chez les concurrents.")

st.caption(
    "ℹ️ Astuce: pour les gros sites (Decathlon, Zalando, etc.), "
    "tu peux coller un cookie de consentement/geo valide si tu en as un. "
    "Sinon, privilégie une **page produit** (les catégories exposent moins de JSON-LD).",
    help=None
)
