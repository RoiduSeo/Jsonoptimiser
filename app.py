import time, random
import streamlit as st
import httpx
from httpx import Timeout

DESKTOP_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

def _base_headers(ua: str):
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        # petits hints modernes (facultatif)
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }

@st.cache_data(show_spinner=False, ttl=60*60)
def fetch_url_html(url: str, timeout_s: int = 30, retries: int = 2) -> str:
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url

    last_err = None
    for attempt in range(retries + 1):
        ua = random.choice(DESKTOP_UAS)
        headers = _base_headers(ua)
        try:
            t = Timeout(connect=10.0, read=timeout_s, write=20.0, pool=5.0)
            # 1) ouvrir la home pour cookies (si possible)
            from urllib.parse import urlparse, urlunparse
            p = urlparse(url)
            origin = urlunparse((p.scheme, p.netloc, "/", "", "", ""))

            with httpx.Client(follow_redirects=True, timeout=t, headers=headers) as client:
                try:
                    client.get(origin)  # set cookies
                except Exception:
                    pass  # la home peut échouer, ce n'est pas bloquant

                # 2) requête page avec Referer
                hdrs = dict(headers)
                hdrs["Referer"] = origin
                resp = client.get(url, headers=hdrs)
                if resp.status_code == 403:
                    # tente une 2e passe avec un autre UA
                    ua2 = random.choice(DESKTOP_UAS)
                    hdrs2 = _base_headers(ua2)
                    hdrs2["Referer"] = origin
                    resp = client.get(url, headers=hdrs2)

                resp.raise_for_status()
                html = resp.text

                # heuristique anti-bot
                low = html.lower()
                if any(s in low for s in ("captcha", "access denied", "are you a robot", "bot detection", "cloudflare")):
                    raise RuntimeError("Page protégée (anti-bot)")

                return html

        except Exception as e:
            last_err = e
            time.sleep(1.2 * (attempt + 1))

    raise last_err
