import streamlit as st
from bs4 import BeautifulSoup
import extruct
from w3lib.html import get_base_url
import json

st.set_page_config(page_title="Comparateur de Données Structurées", layout="wide")

st.title("🔍 Comparateur de Données Structurées")
st.markdown("""
Cet outil permet de comparer les **données structurées** (JSON-LD, Microdata, RDFa) entre votre page et celles de vos concurrents.  
Collez les codes HTML complets ci-dessous.
""")

def extract_structured_data(html_content, url="http://example.com"):
    base_url = get_base_url(html_content, url)
    soup = BeautifulSoup(html_content, 'html.parser')
    extracted = extruct.extract(
        html_content,
        base_url=base_url,
        syntaxes=['json-ld', 'microdata', 'rdfa'],
        uniform=True
    )
    return extracted

# Entrée pour le client
st.header("📌 Code HTML - Votre site")
client_html = st.text_area("Collez ici le code HTML complet de votre page", height=300)

# Entrées pour les concurrents
st.header("🏁 Codes HTML - Concurrents")
competitor_count = st.number_input("Nombre de concurrents à comparer", min_value=1, max_value=5, value=1, step=1)

competitor_htmls = []
for i in range(competitor_count):
    html = st.text_area(f"Concurrents {i+1} - Code HTML complet", key=f"competitor_{i}", height=300)
    competitor_htmls.append(html)

if st.button("🔍 Comparer"):
    if not client_html.strip():
        st.error("Veuillez fournir le code HTML de votre site.")
    else:
        st.subheader("🧾 Données structurées extraites")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown("### 🟢 Votre Site")
            client_data = extract_structured_data(client_html)
            st.json(client_data)

        with col2:
            for idx, html in enumerate(competitor_htmls):
                if html.strip():
                    st.markdown(f"### 🔴 Concurrent {idx+1}")
                    competitor_data = extract_structured_data(html)
                    st.json(competitor_data)
                else:
                    st.warning(f"Pas de code HTML pour le concurrent {idx+1}")

