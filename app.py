import time
import random
import requests
from urllib.parse import urlparse, urljoin

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
        # ces en-têtes “browsery” aident souvent pour 403 soft
        "sec-ch-ua": '"Chromium";v="123", "Not:A-Brand";v="8"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

def smart_get(session, url, timeout=15):
    """Quelques variantes 'propres' avant d’abandonner."""
    tried = set()
    variants = [url]

    # Ajoute une variante avec / final
    if not url.endswith("/"):
        variants.append(url + "/")

    # Ajoute variantes AMP si probable
    if "?" in url:
        variants.append(url + "&amp=1")
    else:
        variants.append(url + "?amp=1")
    if not url.rstrip("/").endswith("/amp"):
        variants.append(url.rstrip("/") + "/amp")

    for u in variants:
        if u in tried:
            continue
        tried.add(u)

        headers = build_headers(u)
        resp = session.get(u, headers=headers, allow_redirects=True, timeout=timeout)
        # 2xx OK
        if 200 <= resp.status_code < 300 and resp.headers.get("content-type","").startswith(("text/html","application/xhtml+xml")):
            return resp
        # 403/406/451 -> réessaie après petite pause
        if resp.status_code in (403, 406, 451):
            time.sleep(0.4 + random.random()*0.6)
            continue
        # 3xx suivi automatiquement, 4xx/5xx autres: on tente la variante suivante
    # Si rien n'a marché, lève la dernière erreur 403 si dispo
    raise requests.HTTPError(f"Échec de récupération (403/AMP/variants) pour {url}")

def fetch_html(url: str, user_agent: str = DEFAULT_UA, timeout: int = 15) -> str:
    if not url:
        return ""
    # robots.txt (on garde ta fonction is_allowed_by_robots si tu l’as)
    if not is_allowed_by_robots(url, user_agent):
        raise PermissionError(f"L’accès à {url} est refusé par robots.txt.")
    with requests.Session() as s:
        s.headers.update(build_headers(url, user_agent))
        resp = smart_get(s, url, timeout=timeout)
        resp.raise_for_status()
        return resp.text or ""
