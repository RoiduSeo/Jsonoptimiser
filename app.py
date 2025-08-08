# ========================
#  🚀 Structured Data Analyser (URLs + HTML)
# ========================
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

st.set_page_config(page_title="🚀 Structured Data Analyser", layout="wide")
st.title("🚀 Structured Data Analyser")

# ------------------------
# 🌐 Récupération HTML avec respect de robots.txt
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
        # Si robots.txt illisible, on suppose autorisé (comportement standard de nombreux clients)
        return True

def fetch_html(url: str, user_agent: str = DEFAULT_UA, timeout: int = 15) -> str:
    if not url:
        return ""
    # Respect robots.txt
    if not is_allowed_by_robots(url, user_agent):
        raise PermissionError(f"L’accès à {url} est refusé par robots.txt.")
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    # Nettoyage léger
    content = resp.text or ""
    # Certaines pages renvoient du XML/xhtml, on garde tel quel
    return content

# ------------------------
# 🔎 Extraction JSON-LD + flatten
# ------------------------
def extract_jsonld_schema(html_content: str, url: str = "http://example.com"):
    base_url = get_base_url(html_content, url)
    data = extruct.extract(
        html_content,
        base_url=base_url,
        syntaxes=["json-ld"],
        uniform=True
    )
    return data.get("json-ld", [])

def flatten_schema(jsonld_data):
    """
    Retourne un set de paires (Type, Propriété).
    On stocke toujours ('Type', '@type') et chaque clé rencontrée pour ce type.
    """
    results = set()
    def recurse(obj, current_type=None):
        if isinstance(obj, dict):
            obj_type = obj.get('@type', current_type)
            if obj_type:
                results.add((obj_type, '@type'))
            for key, value in obj.items():
                if key != '@type':
                    # Si pas de type courant, on étiquette sous 'Unknown'
                    tag_type = obj_type or "Unknown"
                    results.add((tag_type, key))
                    recurse(value, obj_type)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item, current_type)
    recurse(jsonld_data)
    return results

# ------------------------
# 🟢 SAISIE
# ------------------------
st.header("🟢 Votre site")
col1, col2 = st.columns(2)
with col1:
    client_url = st.text_input("URL de la page (votre site)", placeholder="https://…")
with col2:
    client_html = st.text_area("OU collez l’HTML de la page (prioritaire si rempli)", height=160)

st.header("🔴 Concurrents")
competitor_count = st.number_input("Nombre de concurrents", min_value=1, max_value=5, value=1, step=1)

competitor_inputs = []
for i in range(competitor_count):
    st.markdown(f"**Concurrent {i+1}**")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input(f"Nom Concurrent {i+1}", key=f"name_{i}", value=f"Concurrent {i+1}")
        url = st.text_input(f"URL Concurrent {i+1}", key=f"url_{i}", placeholder="https://…")
    with c2:
        html = st.text_area(f"OU HTML Concurrent {i+1}", key=f"html_{i}", height=140)
    competitor_inputs.append((name, url, html))

st.caption("💡 L’outil tente de télécharger les pages. Si une page est protégée (paywall, auth, CAPTCHA, ou interdite via robots.txt), colle le HTML manuellement.")

# ------------------------
# 🔍 COMPARAISON
# --------------
