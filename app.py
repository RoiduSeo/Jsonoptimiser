# =====================================================
# 🚀 Structured Data Analyser — ignore toujours robots.txt
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
</style>
"""
st.markdown(COMPACT_CSS, unsafe_allow_html=True)
st.markdown("## 🚀 Structured Data Analyser")

# ------------------------
# 🌐 Récup HTML (robots.txt ignoré) + headers “navigateur”
# ------------------------
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

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
    tried = set()
    for u in variants:
        if u in tried: continue
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
def fetch_html(url: str, timeout: int = 15) -> str:
    if not url:
        return ""
    with requests.Session() as s:
        s.headers.update(build_headers(url))
        resp = smart_get(s, url, timeout=timeout)
        resp.raise_for_status()
        return resp.text or ""

# ------------------------
# 🔎 Extraction JSON-LD + flatten
# ------------------------
def extract_jsonld_schema(html_content: str, url: str = "http://example.com"):
    base_url = get_base_url(html_content, url)
    data = extruct.extract(html_content, base_url=base_url, syntaxes=["json-ld"], uniform=True)
    return data.get("json-ld", [])

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

    run = st.button("🔍 Lancer l’analyse")

# ------------------------
# Analyse
# ------------------------
def analyze_once(client_url, client_html, competitor_entries):
    if client_html.strip():
        client_html_final = client_html
        client_eff_url = client_url or "http://example.com"
    elif client_url.strip():
        client_html_final = fetch_html(client_url)
        client_eff_url = client_url
    else:
        st.error("Merci de fournir au moins l’URL ou l’HTML de votre page.")
        st.stop()

    client_pairs = build_pairs_from_html(client_html_final, client_eff_url)

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
                comp_html = fetch_html(url)
                comp_eff_url = url
            else:
                st.warning(f"[{comp_name}] Pas d’URL ni HTML — ignoré.")
                competitor_pairs_list.append(set())
                continue
            pairs = build_pairs_from_html(comp_html, comp_eff_url)
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
            name = competitor_names[i]
            row[name] = has_it
        if row["Votre site"] == "❌" and at_least_one:
            missing.append((item_type, prop))
        rows.append(row)

    df = pd.DataFrame(rows)
    return df, missing, competitor_names

if run:
    try:
        st.session_state.results = analyze_once(client_url, client_html, competitor_entries)
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
            st.info("Aucune donnée JSON-LD détectée.")
            st.stop()

        show_only_missing = st.toggle("Afficher uniquement les propriétés manquantes", value=False)
        view_df = df[df["Votre site"].eq("❌")].copy() if show_only_missing else df.copy()

        types = list(view_df["Type"].dropna().unique())
        sel_col1, sel_col2 = st.columns([3, 9])
        with sel_col1:
            selected_type = st.selectbox("Types détectés", options=["(Tous)"] + types, index=0)
        with sel_col2:
            if selected_type != "(Tous)":
                st.markdown(f"#### 📂 {selected_type}")
                sub = view_df[view_df["Type"] == selected_type].copy()
                check_cols = [c for c in sub.columns if c not in ("Type", "Propriété")]
                styled = sub[["Propriété"] + check_cols].style.applymap(colorize, subset=check_cols)
                st.dataframe(styled, use_container_width=True)
            else:
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
