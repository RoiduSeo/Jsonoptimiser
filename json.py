import streamlit as st
from bs4 import BeautifulSoup
import extruct
from w3lib.html import get_base_url
import pandas as pd
import json
import datetime
import httpx
from urllib.parse import urlparse

st.set_page_config(page_title="🚀 Structured Data Analyser", layout="wide")
st.title("🚀 Structured Data Analyser")

# ------------------------
# ⚙️ Utils
# ------------------------

@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_url_html(url: str, timeout: int = 20, render_js: bool = False) -> str:
    """
    Récupère le HTML d'une URL.
    - render_js: placeholder (False par défaut). Si tu veux activer Playwright plus tard,
      tu pourras remplacer ce bloc.
    """
    # Normalisation très simple
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    with httpx.Client(follow_redirects=True, headers=headers, timeout=timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

    # Optionnel: si tu ajoutes Playwright, tu peux rendre le JS ici quand render_js=True
    return html

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

def extract_from_input(html_or_url: str, mode: str):
    """
    mode: 'url' ou 'html'
    Retourne un set((type, prop)) et le html récupéré (pour debug éventuel).
    """
    if mode == "url":
        html = fetch_url_html(html_or_url)
        base_url = html_or_url
    else:
        html = html_or_url
        base_url = "http://example.com"

    data = extract_jsonld_schema(html, url=base_url)
    schema = set()
    for block in data:
        schema |= flatten_schema(block)
    return schema, html

def host_from_url(u: str) -> str:
    try:
        h = urlparse(u).netloc
        return h if h else u
    except Exception:
        return u

# ------------------------
# 🟢 ZONE DE SAISIE
# ------------------------

st.header("🟢 Votre site")

input_mode = st.radio(
    "Mode d'entrée",
    ["URL (recommandé)", "Coller du HTML"],
    horizontal=True,
)

if input_mode == "URL (recommandé)":
    client_url = st.text_input("URL de votre site", placeholder="https://www.exemple.com")
    client_html = ""  # pas utilisé
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
            url = st.text_input(f"URL du concurrent {i+1}", key=f"url_{i}", placeholder="https://www.exemple.com")
            name_default = host_from_url(url) if url else f"Concurrent {i+1}"
            name = st.text_input(f"Nom affiché (optionnel) {i+1}", value=name_default, key=f"name_{i}")
            competitors.append({"name": name or f"Concurrent {i+1}", "mode": "url", "value": url})
        else:
            name = st.text_input(f"Nom du site Concurrent {i+1}", key=f"name_{i}", value=f"Concurrent {i+1}")
            html = st.text_area(f"Code HTML - {name}", key=f"competitor_{i}", height=200)
            competitors.append({"name": name, "mode": "html", "value": html})

# ------------------------
# 🔍 COMPARAISON
# ------------------------

if st.button("🔍 Comparer les schémas"):
    # Validations simples
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
            client_schema, _client_html_dbg = extract_from_input(client_url or client_html, client_mode)
        except Exception as e:
            st.error(f"Erreur lors de l'extraction du site client : {e}")
            st.stop()

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
                competitor_schemas.append(set())  # vide
                continue
            try:
                comp_schema, _ = extract_from_input(value, "url" if mode == "url" else "html")
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

    # ------------------------
    # 📊 TABLEAU COMPARATIF PAR TYPE
    # ------------------------
    st.subheader("🧩 Données comparées par type")
    grouped = df.groupby("Type", dropna=False)

    def colorize(val):
        return "color: green" if val == "✅" else "color: red"

    for group_type, group_df in grouped:
        with st.expander(f"📂 {group_type}", expanded=False):
            styled_group = group_df.style.applymap(colorize, subset=group_df.columns[2:])
            st.dataframe(styled_group, use_container_width=True)

    # ------------------------
    # 📌 RAPPORT OPPORTUNITÉS
    # ------------------------
    with st.expander("📌 Rapport d'opportunités manquantes", expanded=True):
        st.markdown(f"**Nombre total d'opportunités manquantes sur votre site :** `{len(missing_opportunities)}`")
        if missing_opportunities:
            oppo_df = pd.DataFrame(missing_opportunities, columns=["Type", "Propriété"])
            st.dataframe(oppo_df, use_container_width=True)
        else:
            st.success("🎉 Votre site contient toutes les données structurées détectées chez les concurrents.")

    # ------------------------
    # 🛠️ GÉNÉRER JSON-LD À AJOUTER
    # ------------------------
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
                block = {
                    "@context": "https://schema.org",
                    "@type": schema_type
                }
                block.update(props)
                generated_jsonld.append(block)

            editable_json = json.dumps(generated_jsonld, indent=2, ensure_ascii=False)
            user_json = st.text_area("✍️ JSON-LD généré automatiquement (modifiable)", value=editable_json, height=300)

            st.download_button(
                label="📥 Télécharger le JSON-LD",
                data=user_json,
                file_name=f"donnees-structurees-{datetime.date.today()}.json",
                mime="application/json"
            )

            st.markdown(
                "👉 Copiez ce code dans une balise "
                "`<script type=\"application/ld+json\">` pour l'intégrer dans votre site."
            )
        else:
            st.info("Aucune donnée à générer. Votre site est complet sur les données analysées.")
