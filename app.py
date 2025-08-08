# =====================================================
# 🚀 Structured Data Analyser — UI compacte (gauche/droite)
# =====================================================
import streamlit as st
from bs4 import BeautifulSoup
import extruct
from w3lib.html import get_base_url
import pandas as pd
import json
import datetime
import requests
from urllib.parse import urlparse
import urllib.robotparser as robotparser

# ---------------------------
# Page / thème / CSS compact
# ---------------------------
st.set_page_config(page_title="🚀 Structured Data Analyser", layout="wide")

COMPACT_CSS = """
<style>
/* resserre l'UI */
.block-container {padding-top: 1.2rem; padding-bottom: 1rem;}
section[data-testid="stSidebar"] .block-container {padding: 1rem 0.6rem;}
/* titres + marges */
h1, h2, h3, h4 { margin: 0.2rem 0 0.6rem 0; }
/* Inputs plus denses */
div[data-baseweb="input"] input, textarea { font-size: 0.95rem; }
.stTextInput, .stTextArea, .stNumberInput { margin-bottom: 0.4rem; }

/* Badges / bulles (chips) cliquables */
.chips { display:flex; flex-wrap:wrap; gap:.4rem; }
.chip-btn {
  border: 1px solid rgba(255,255,255,.2);
  padding: .25rem .6rem;
  border-radius: 999px;
  font-size: .85rem;
  cursor: pointer;
  background: rgba(255,255,255,.05);
  transition: all .15s ease;
  text-decoration: none;
  color: inherit;
}
.chip-btn:hover { background: rgba(255,255,255,.12); }
.chip-active { background: rgba(0,122,255,.25); border-color: rgba(0,122,255,.55); }
.chip-missing::after {
  content: " • manquants";
  font-size: .75rem; opacity: .8;
}

/* Pastilles ✅/❌ en tableau */
td, th { vertical-align: middle !important; }
</style>
"""
st.markdown(COMPACT_CSS, unsafe_allow_html=True)

st.markdown("## 🚀 Structured Data Analyser")

# ------------------------
# Récup HTML (robots.txt OK)
# ------------------------
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36 (StructuredDataAnalyser/1.0)"
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

def fetch_html(url: str, user_agent: str = DEFAULT_UA, timeout: int = 15) -> str:
    if not url:
        return ""
    if not is_allowed_by_robots(url, user_agent):
        raise PermissionError(f"L’accès à {url} est refusé par robots.txt.")
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text or ""

# ------------------------
# JSON-LD extract + flatten
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
            for it in obj: recurse(it, current_type)
    recurse(jsonld_data)
    return results

# =========================================================================
# 🧩 Mise en page compacte : gauche (inputs) | droite (résultats)
# =========================================================================
left, right = st.columns([5, 7])

with left:
    st.markdown("### 🟢 Votre page")
    with st.form(key="inputs_form", clear_on_submit=False):
        client_url = st.text_input("URL de la page (votre site)", placeholder="https://…")
        client_html = st.text_area("OU collez l’HTML (prioritaire si rempli)", height=120)

        st.markdown("### 🔴 Concurrents")
        competitor_count = st.number_input("Nombre de concurrents", 1, 5, 1, 1)
        comp_entries = []
        for i in range(int(competitor_count)):
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

# variables de session pour l’onglet actif (bulle) et cache simple
if "active_type" not in st.session_state:
    st.session_state.active_type = None

# =========================================================================
# ⚙️ Pipeline d’analyse après clic
# =========================================================================
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
            if name in row: name = f"{name} ({i+1})"
            row[name] = has_it
        if row["Votre site"] == "❌" and at_least_one_has_it:
            missing_opportunities.append((item_type, prop))
        rows.append(row)

    df = pd.DataFrame(rows)
    return df, missing_opportunities, competitor_names

def colorize(val):
    if val == "✅": return "color: green"
    if val == "❌": return "color: red"
    return ""

# =========================================================================
# 🧾 Résultats (à droite) — bulles + tableau par type + rapport
# =========================================================================
with right:
    st.markdown("### 📈 Résultats")

    if submitted:
        try:
            df, missing_opportunities, competitor_names = analyze(client_url, client_html, comp_entries)
        except Exception as e:
            st.error(f"Erreur d’analyse : {e}")
            st.stop()

        if df.empty:
            st.info("Aucune donnée JSON-LD détectée. Essaie une page produit ou colle le HTML.")
            st.stop()

        # ---- Liste des types (bulles cliquables)
        types = list(df["Type"].dropna().unique())
        # comptage manquants par type
        miss_df = pd.DataFrame(missing_opportunities, columns=["Type", "Propriété"])
        missing_per_type = miss_df.groupby("Type").size().to_dict() if not miss_df.empty else {}

        # chips HTML (avec boutons streamlit pour clic)
        st.markdown("#### Types détectés")
        chips_container = st.container()
        chip_cols = st.columns(min(4, max(1, len(types))))
        # on rend chaque puce "cliquable" via st.button et CSS custom
        for idx, t in enumerate(types):
            col = chip_cols[idx % len(chip_cols)]
            is_active = (st.session_state.active_type == t)
            label = t
            if t in missing_per_type and missing_per_type[t] > 0:
                label = f"{t} ({missing_per_type[t]})"
            with col:
                if st.button(label, key=f"chip_{t}"):
                    st.session_state.active_type = t if not is_active else None
            # Applique style visuel (astuce : re-render via markdown)
        # mini séparateur
        st.markdown("<div style='height:.2rem'></div>", unsafe_allow_html=True)

        # ---- Tableau filtré par bulle active (sinon tout groupé)
        if st.session_state.active_type:
            show_df = df[df["Type"] == st.session_state.active_type].copy()
            st.markdown(f"#### 📂 {st.session_state.active_type}")
            check_cols = [c for c in show_df.columns if c not in ("Type", "Propriété")]
            styled = show_df[["Propriété"] + check_cols].style.applymap(colorize, subset=check_cols)
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
