import streamlit as st
from bs4 import BeautifulSoup
import extruct
from w3lib.html import get_base_url
import pandas as pd
import json

st.set_page_config(page_title="Comparateur de Données Structurées", layout="wide")

st.title("🔎 Comparateur Structuré de Données JSON-LD")
st.markdown("""
Collez le **code HTML complet** de votre site et de ceux de vos concurrents.  
L'outil extrait les schémas JSON-LD et affiche un **tableau comparatif clair**.
""")

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
    """Transforme une liste de blocs JSON-LD en un set de tuples (type, propriété)"""
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

st.header("📌 Votre site")
client_html = st.text_area("Code HTML complet de votre site", height=250)

st.header("🏁 Concurrents")
competitor_count = st.number_input("Nombre de concurrents", min_value=1, max_value=5, value=1, step=1)

competitor_htmls = []
for i in range(competitor_count):
    html = st.text_area(f"Concurrent {i+1} - Code HTML complet", key=f"competitor_{i}", height=250)
    competitor_htmls.append(html)

if st.button("🔍 Comparer les schémas"):
    if not client_html.strip():
        st.error("Merci de fournir le code HTML de votre site.")
    else:
        st.subheader("📊 Résultat Comparatif")

        # Extraction des données structurées
        client_data = extract_jsonld_schema(client_html)
        client_schema = set()
        for block in client_data:
            client_schema |= flatten_schema(block)

        all_keys = set(client_schema)
        competitor_schemas = []
        for html in competitor_htmls:
            comp_data = extract_jsonld_schema(html)
            comp_schema = set()
            for block in comp_data:
                comp_schema |= flatten_schema(block)
            competitor_schemas.append(comp_schema)
            all_keys |= comp_schema

        # Création du tableau
        rows = []
        for item_type, prop in sorted(all_keys):
            row = {
                "Type": item_type,
                "Propriété": prop,
                "Votre site": "✅" if (item_type, prop) in client_schema else "❌"
            }
            for i, comp_schema in enumerate(competitor_schemas):
                row[f"Concurrent {i+1}"] = "✅" if (item_type, prop) in comp_schema else "❌"
            rows.append(row)

        df = pd.DataFrame(rows)
        # Coloration conditionnelle
        def colorize(val):
            return "color: green" if val == "✅" else "color: red"

        styled_df = df.style.applymap(colorize, subset=df.columns[2:])
        st.dataframe(styled_df, use_container_width=True)
