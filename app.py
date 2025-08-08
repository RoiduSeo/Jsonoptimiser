# =====================================================
# 🚀 Structured Data Analyser — compact UI (left inputs | right results)
# =====================================================
import streamlit as st
from bs4 import BeautifulSoup  # optionnel, mais on garde si besoin de parsing plus tard
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

/* chips (bulles) */
.chips { display:flex; flex-wrap:wrap; gap:.4rem; }
.chip-btn {
  border: 1px solid rgba(255,255,255,.2);
  padding: .25rem .6rem;
  border-radius: 999px;
  font-size: .85rem;
  cursor: pointer;
  background: rgba(255,255,255,.05);
  transition: all .15s ease; color: inherit;
}
.chip-btn:hover { background: rgba(255,255,255,.12); }
.chip-active { background: rgba(0,122,255,.25); border-color: rgba(0,122,255,.55); }

/* tableaux plus denses */
td, th { vertical-align: middle !important; }
</style>
"""
st.markdown(COMPACT_CSS, unsafe_allow_html=True)
st.markdown("## 🚀 Structured Data Analyser")

# ------------------------
# 🌐 Récup HTML avec respect de robots.txt et headers “navigateur”
# ------------------------
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

def is_allowed_by_robots(url: str, user_agent: str = DEFAULT_UA) -> bool:
    """Respecte robots.txt (si illisible, on suppose OK)."""
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True

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

    # Variante avec slash final
    if not url.endswith("/"):
        variants.append(url + "/")

    # Variantes AMP
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
                # petit backoff aléatoire puis on tente la prochaine variante
                time.sleep(0.4 + random.random() * 0.6)
                continue
        except Exception as e:
            last_exc = e
            time.sleep(0.2)
            continue

    if last_exc:
        raise last_exc
    raise requests.HTTPError(f"Échec de récupération (403/variants) pour {url}")

def fetch_html(url: str, user_agent: str = DEFAULT_UA, timeout: int = 15) -> str:
    if not url:
        return ""
    if not is_allowed_by_robots(url, user_agent):
        raise PermissionError(f"L’accès à {url} est refusé par robots.txt.")
    with requests.Session() as s:
        s.headers.update(build_headers(url, user_agent))
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

def colorize(val):
    if val == "✅": return "color: green"
    if val == "❌": return "color: red"
    return ""

# ------------------------
# 🧩 Layout : gauche (inputs) | droite (résultats)
# ------------------------
left, right = st.columns([5, 7])

# État UI
if "active_type" not in st.session_state:
    st.session_state.active_type = None
if "competitor_count" not in st.session_state:
    st.session_state.competitor_count = 1

with left:
    st.markdown("### 🟢 Votre page")
    client_url = st.text_input("URL de la page (votre site)", placeholder="https://…")
    client_html = st.text_area("OU collez l’HTML (prioritaire si rempli)", height=120)

    st.markdown("### 🔴 Concurrents")
    # Nombre de concurrents en dehors du form -> les champs apparaissent immédiatement
    st.session_state.competitor_count = st.number_input(
        "Nombre de concurrents", min_value=1, max_value=5, value=st.session_state.competitor_count, step=1
    )

    with st.form(key="inputs_form", clear_on_submit=False):
        comp_entries = []
        for i in range(int(st.session_state.competitor_count)):
            st.markdown(f"**Concurrent {i+1}**")
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input(f"Nom {i+1}", key=f"name_{i}", value=f"Concurrent {i+1}")
                url = st.text_input(f"URL {i+1}", key=f"url_{i}", placeholder="https://…")
            with c2:
                html = st.text_area(f"HTML {i+1}", key=f"html_{i}", height=90)
            comp_entries.append((name, url, html))

        st.caption("💡 Si une page est protégée (paywall/auth/CAPTCHA/robots.txt), colle le HTML.")
        submitted = st.form_submit_button("🔍 Lancer l’analyse")

# ------------------------
# ⚙️ Analyse
# ------------------------
def analyze(client_url, client_html, comp_entries):
    # --- Client
    if client_html.strip():
        client_raw_html = client_html
        client_eff_url = client_url or "http://example.com"
    elif client_url.strip():
        client_raw_html = fetch_html(client_url)
        client_eff_url = client_url
    else:
        st.error("Merci de fournir au moins l’URL ou l’HTML de votre page.")
        st.stop()

    client_data = extract_jsonld_schema(client_raw_html, url=client_eff_url)
    client_schema = set()
    for block in client_data:
        client_schema |= flatten_schema(block)

    # --- Concurrents
    competitor_names = []
    competitor_schemas = []
    all_keys = set(client_schema)

    for i, (name, url, html) in enumerate(comp_entries):
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
                competitor_schemas.append(set())
                continue
        except PermissionError as e:
            st.warning(f"[{comp_name}] {e}")
            competitor_schemas.append(set()); continue
        except Exception as e:
            st.warning(f"[{comp_name}] Récupération impossible : {e}")
            competitor_schemas.append(set()); continue

        comp_data = extract_jsonld_schema(comp_html, url=comp_eff_url)
        comp_schema = set()
        for block in comp_data:
            comp_schema |= flatten_schema(block)
        competitor_schemas.append(comp_schema)
        all_keys |= comp_schema

    # --- Table
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
            if has_it == "✅": at_least_one_has_it = True
            name = competitor_names[i]
            if name in row:  # évite collision de clé
                name = f"{name} ({i+1})"
            row[name] = has_it
        if row["Votre site"] == "❌" and at_least_one_has_it:
            missing_opportunities.append((item_type, prop))
        rows.append(row)

    df = pd.DataFrame(rows)
    return df, missing_opportunities, competitor_names

# ------------------------
# 🧾 Résultats (droite)
# ------------------------
with right:
    st.markdown("### 📈 Résultats")

    if submitted:
        try:
            df, missing_opportunities, competitor_names = analyze(client_url, client_html, comp_entries)
        except Exception as e:
            st.error(f"Erreur d’analyse : {e}")
            st.stop()

        if df.empty or "Type" not in df.columns:
            st.info("Aucune donnée JSON-LD détectée. Essaie une page produit ou colle le HTML.")
            st.stop()

        # Toggle pour n’afficher que les propriétés manquantes
        show_only_missing = st.toggle(
            "Afficher uniquement les propriétés manquantes sur votre site", value=False
        )
        if show_only_missing:
            df = df[df["Votre site"].eq("❌")].copy()
            if df.empty:
                st.success("🎉 Aucune propriété manquante sur votre site selon cette analyse.")
                st.stop()

        # ---- Chips / bulles de types
        types = list(df["Type"].dropna().unique())

        miss_df = pd.DataFrame(missing_opportunities, columns=["Type", "Propriété"])
        missing_per_type = miss_df.groupby("Type").size().to_dict() if not miss_df.empty else {}

        st.markdown("#### Types détectés")
        chip_cols = st.columns(min(4, max(1, len(types))))
        for idx, t in enumerate(types):
            col = chip_cols[idx % len(chip_cols)]
            label = t if t not in missing_per_type else f"{t} ({missing_per_type[t]})"
            with col:
                if st.button(label, key=f"chip_{t}"):
                    # toggle
                    st.session_state.active_type = None if st.session_state.active_type == t else t

        st.markdown("<div style='height:.2rem'></div>", unsafe_allow_html=True)

        # ---- Tableau filtré par bulle active (sinon groupé)
        if st.session_state.active_type:
            sub = df[df["Type"] == st.session_state.active_type].copy()
            st.markdown(f"#### 📂 {st.session_state.active_type}")
            check_cols = [c for c in sub.columns if c not in ("Type", "Propriété")]
            styled = sub[["Propriété"] + check_cols].style.applymap(colorize, subset=check_cols)
            st.dataframe(styled, use_container_width=True)
        else:
            st.markdown("#### 🧩 Données comparées par type")
            grouped = df.groupby("Type", dropna=False)
            for t, sub in grouped:
                with st.expander(f"📂 {t}", expanded=False):
                    check_cols = [c for c in sub.columns if c not in ("Type", "Propriété")]
                    styled = sub[["Propriété"] + check_cols].style.applymap(colorize, subset=check_cols)
                    st.dataframe(styled, use_container_width=True)

        # ---- Rapport opportunités
        st.markdown("#### 📌 Rapport d’opportunités")
        st.markdown(f"**Total manquants :** `{len(missing_opportunities)}`")
        if missing_opportunities:
            opp_df = pd.DataFrame(sorted(missing_opportunities), columns=["Type", "Propriété"])
            st.dataframe(opp_df, use_container_width=True)
        else:
            st.success("🎉 Votre page contient toutes les données détectées chez les concurrents.")

        # ---- Générateur JSON-LD
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
                user_json = st.text_area("✍️ JSON-LD généré (modifiable)", value=editable_json, height=260)
                st.download_button(
                    label="📥 Télécharger le JSON-LD",
                    data=user_json,
                    file_name=f"donnees-structurees-{datetime.date.today()}.json",
                    mime="application/json"
                )
            else:
                st.info("Aucune donnée à générer.")
    else:
        st.info("⚡ Renseigne les URLs/HTML à gauche puis clique **Lancer l’analyse**.")
