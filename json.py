import streamlit as st
from bs4 import BeautifulSoup
import extruct
from w3lib.html import get_base_url
import pandas as pd
import json
import datetime

st.set_page_config(page_title="🚀 Structured Data Analyser", layout="wide")

st.title("🚀 Structured Data Analyser")

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

# ------------------------
# 🟢 ZONE DE SAISIE
# ------------------------

st.header("🟢 Votre site")
client_html = st.text_area("Code HTML complet de votre site", height=250)

st.header("🔴 Concurrents")
competitor_count = st.number_input("Nombre de concurrents", min_value=1, max_value=5, value=1, step=1)

competitor_htmls = []
competitor_names = []
for i in range(competitor_count):
    name = st.text_input(f"Nom du site Concurrent {i+1}", key=f"name_{i}", value=f"Concurrent {i+1}")
    html = st.text_area(f"Code HTML - {name}", key=f"competitor_{i}", height=250)
    competitor_names.append(name)
    competitor_htmls.append(html)

# ------------------------
# 🔍 COMPARAISON
# ------------------------

if st.button("🔍 Comparer les schémas"):
    if not client_html.strip():
        st.error("Merci de fournir le code HTML de votre site.")
    else:
        st.header("📈 Résultat Comparatif")

        # Extraction client
        client_data = extract_jsonld_schema(client_html)
        client_schema = set()
        for block in client_data:
            client_schema |= flatten_schema(block)

        # Extraction concurrents
        all_keys = set(client_schema)
        competitor_schemas = []
        for html in competitor_htmls:
            comp_data = extract_jsonld_schema(html)
            comp_schema = set()
            for block in comp_data:
                comp_schema |= flatten_schema(block)
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

        st.subheader("🧩 Données Comparées par Type")
        grouped = df.groupby("Type")
        for group_type, group_df in grouped:
            with st.expander(f"📂 {group_type}"):
                def colorize(val):
                    return "color: green" if val == "✅" else "color: red"
                styled_group = group_df.style.applymap(colorize, subset=group_df.columns[2:])
                st.dataframe(styled_group, use_container_width=True)

        # ------------------------
        # 📌 RAPPORT OPPORTUNITÉS
        # ------------------------

        with st.expander("📌 Rapport d'Opportunités Manquantes", expanded=True):
            st.markdown(f"**Nombre total d'opportunités manquantes sur votre site :** `{len(missing_opportunities)}`")
            if missing_opportunities:
                oppo_df = pd.DataFrame(missing_opportunities, columns=["Type", "Propriété"])
                st.dataframe(oppo_df)
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

                st.markdown("👉 Copiez ce code dans une balise `<script type=\"application/ld+json\">` pour l'intégrer dans votre site.")
            else:
                st.info("Aucune donnée à générer. Votre site est complet sur les données analysées.")
