#!/usr/bin/env python3
"""
Bitácora Financiera — actualizador diario.

Jala los feeds RSS configurados abajo, extrae título/link/imagen/fecha
de cada nota, y escribe docs/data/news.json — que es lo que consume
docs/index.html en el navegador.

IMPORTANTE: las URLs de RSS de abajo son las rutas públicas conocidas de
cada medio al momento de escribir este script. Los medios cambian sus
feeds sin avisar y algunos (ej. Bloomberg, WSJ, The Economist en ciertas
secciones) restringen o eliminan el RSS público con el tiempo. Antes de
confiar en este script:
  1. Corre `python scripts/fetch_news.py` localmente una vez.
  2. Revisa el log — te dice qué feeds sí respondieron y cuáles fallaron.
  3. Ajusta o quita las URLs muertas en SOURCES.

Un feed roto NUNCA tumba la corrida completa: se salta con un warning.
"""

import json
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

# ---------------------------------------------------------------------------
# Configuración de fuentes por sección. Agrega/edita libremente.
# "rss": URL del feed. "max": cuántas notas tomar de esa fuente.
# ---------------------------------------------------------------------------
SOURCES = {
    "global": [
        {"name": "Reuters Business", "rss": "https://www.reutersagency.com/feed/?best-topics=business-finance", "max": 6},
        {"name": "The Economist — Finance", "rss": "https://www.economist.com/finance-and-economics/rss.xml", "max": 6},
        {"name": "Bloomberg Markets", "rss": "https://feeds.bloomberg.com/markets/news.rss", "max": 6},
    ],
    "wallstreet": [
        {"name": "WSJ Markets", "rss": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "max": 6},
        {"name": "CNBC Top News", "rss": "https://www.cnbc.com/id/10001147/device/rss/rss.html", "max": 6},
        {"name": "MarketWatch Top Stories", "rss": "https://feeds.marketwatch.com/marketwatch/topstories/", "max": 6},
    ],
    "fintech": [
        {"name": "Forbes Business", "rss": "https://www.forbes.com/business/feed/", "max": 6},
        {"name": "Yahoo Finance", "rss": "https://finance.yahoo.com/news/rssindex", "max": 6},
        {"name": "Global Finance Magazine", "rss": "https://gfmag.com/feed/", "max": 6},
    ],
    "mexico": [
        {"name": "El Financiero", "rss": "https://www.elfinanciero.com.mx/arc/outboundfeeds/rss/", "max": 8},
        {"name": "El Economista", "rss": "https://www.eleconomista.com.mx/rss", "max": 8},
        {"name": "Forbes México", "rss": "https://www.forbes.com.mx/feed/", "max": 6},
        {"name": "Expansión", "rss": "https://expansion.mx/rss", "max": 8},
        {"name": "El Universal — Cartera", "rss": "https://www.eluniversal.com.mx/rss.xml", "max": 6},
        {"name": "Milenio — Negocios", "rss": "https://www.milenio.com/rss/negocios.xml", "max": 6},
    ],
    "guatemala": [
        {"name": "Prensa Libre — Economía", "rss": "https://www.prensalibre.com/arc/outboundfeeds/rss/category/economia/", "max": 8},
        {"name": "La Hora", "rss": "https://lahora.gt/feed/", "max": 6},
        {"name": "Diario de Centroamérica", "rss": "https://www.dca.gob.gt/feed/", "max": 6},
    ],
    "elsalvador": [
        {"name": "El Diario de Hoy", "rss": "https://www.elsalvador.com/rss/", "max": 8},
        {"name": "Diario El Mundo", "rss": "https://diario.elmundo.sv/feed/", "max": 6},
        {"name": "Diario El Salvador", "rss": "https://diarioelsalvador.com/feed/", "max": 6},
    ],
}

USER_AGENT = "BitacoraFinanciera/1.0 (+personal news aggregator)"


def extract_image(entry):
    """Busca imagen en los campos donde los distintos CMS la ponen."""
    if "media_content" in entry and entry.media_content:
        url = entry.media_content[0].get("url")
        if url:
            return url
    if "media_thumbnail" in entry and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get("url")
        if url:
            return url
    if "links" in entry:
        for link in entry.links:
            if link.get("type", "").startswith("image/"):
                return link.get("href")
    if "summary" in entry and "<img" in entry.summary:
        import re
        m = re.search(r'<img[^>]+src="([^"]+)"', entry.summary)
        if m:
            return m.group(1)
    return None


def parse_date(entry):
    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
            except Exception:
                pass
    return None


def fetch_source(source):
    stories = []
    try:
        parsed = feedparser.parse(source["rss"], agent=USER_AGENT)
        if parsed.bozo and not parsed.entries:
            raise ValueError(str(parsed.bozo_exception))
        for entry in parsed.entries[: source.get("max", 6)]:
            stories.append({
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", ""),
                "image": extract_image(entry),
                "source": source["name"],
                "published": parse_date(entry),
            })
        print(f"  ✓ {source['name']}: {len(stories)} notas")
    except Exception as exc:
        print(f"  ✗ {source['name']} — feed falló, se omite ({exc})", file=sys.stderr)
    return stories


def build():
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "sections": {}}
    for section, sources in SOURCES.items():
        print(f"Sección: {section}")
        all_stories = []
        for source in sources:
            all_stories.extend(fetch_source(source))
            time.sleep(0.5)  # ser buen vecino con los servidores de cada medio
        all_stories.sort(key=lambda s: s["published"] or "", reverse=True)
        result["sections"][section] = all_stories
    return result


if __name__ == "__main__":
    data = build()
    with open("docs/data/news.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    total = sum(len(v) for v in data["sections"].values())
    print(f"\nListo: {total} notas escritas en docs/data/news.json")
