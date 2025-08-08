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
        "sec-ch-ua": '"Chromium";v="123", "

