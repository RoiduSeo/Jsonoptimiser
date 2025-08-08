# --- en haut des imports
import time
from httpx import Timeout

# --- options UI (dans la sidebar de préférence)
with st.sidebar:
    st.header("⚙️ Options réseau")
    TIMEOUT_S = st.slider("Timeout (secondes)", 5, 60, 25, 1)
    RETRIES = st.slider("Retries", 0, 5, 2, 1)
    RENDER_JS = st.checkbox("Rendre le JS (Playwright) [expérimental]", value=False,
                            help="À activer plus tard, nécessite Playwright sur l’hébergement.")

# --- remplace fetch_url_html par ceci
@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_url_html(url: str, timeout_s: int = 25, retries: int = 2) -> str:
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url

    headers = {
        # UA réaliste
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
    }

    last_err = None
    for attempt in range(retries + 1):
        try:
            t = Timeout(connect=10.0, read=timeout_s, write=20.0, pool=5.0)
            with httpx.Client(follow_redirects=True, headers=headers, timeout=t, http2=True) as client:
                resp = client.get(url)
                # Quelques sites renvoient 403/429: on tente un 2e UA simplifié en retry
                if resp.status_code >= 400:
                    resp.raise_for_status()
                html = resp.text

                # Détection basique des pages anti-bot
                if any(x in html.lower() for x in [
                    "bot detection", "are you a robot", "captcha", "automated access", "to discuss automated access"
                ]):
                    raise RuntimeError("Page protégée (anti-bot)")
                return html

        except Exception as e:
            last_err = e
            # backoff simple
            time.sleep(1.5 * (attempt + 1))

    # si tous les essais échouent:
    raise last_err
