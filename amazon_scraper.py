"""
Phase 0 — Amazon Best Sellers scraper
Scrapes public bestseller pages. No API key needed.
Returns a list of product dicts with rank, title, price, category.
"""

import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from config import AMAZON_CATEGORIES, AMAZON_TOP_N, AMAZON_REQUEST_DELAY, USER_AGENTS

log = logging.getLogger(__name__)

BASE_URL = "https://www.amazon.com/gp/bestsellers/{category}"

HEADERS_BASE = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "DNT": "1",
}


def _get_headers() -> dict:
    """Return headers with a random user agent."""
    return {**HEADERS_BASE, "User-Agent": random.choice(USER_AGENTS)}


def _parse_bestsellers_page(html: str, category: str) -> list[dict]:
    """Parse one Amazon bestsellers page and return product list."""
    soup = BeautifulSoup(html, "html.parser")
    products = []

    # Amazon renders bestsellers inside div elements with this class
    items = soup.select("div.zg-grid-general-faceout")

    for rank, item in enumerate(items[:AMAZON_TOP_N], start=1):
        # Title
        title_el = item.select_one("div.p13n-sc-truncate-desktop-type2, span.p13n-sc-truncate")
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            continue

        # Price (optional — not always present)
        price_el = item.select_one("span.p13n-sc-price")
        price_text = price_el.get_text(strip=True) if price_el else "N/A"

        # Product URL
        link_el = item.select_one("a.a-link-normal")
        url = "https://www.amazon.com" + link_el["href"] if link_el else ""

        products.append({
            "title":    title,
            "rank":     rank,
            "price":    price_text,
            "category": category,
            "url":      url,
            "source":   "amazon",
        })

    log.info("Amazon [%s]: found %d products", category, len(products))
    return products


def scrape_amazon_bestsellers() -> list[dict]:
    """
    Scrape all configured Amazon bestseller categories.
    Returns merged list, deduplicated by title.
    """
    session = requests.Session()
    all_products = []
    seen_titles = set()

    for category in AMAZON_CATEGORIES:
        url = BASE_URL.format(category=category)
        try:
            resp = session.get(url, headers=_get_headers(), timeout=15)
            if resp.status_code == 503:
                log.warning("Amazon blocked request for [%s] — skipping", category)
                continue
            resp.raise_for_status()

            products = _parse_bestsellers_page(resp.text, category)
            for p in products:
                key = p["title"].lower()[:60]
                if key not in seen_titles:
                    seen_titles.add(key)
                    all_products.append(p)

        except requests.RequestException as e:
            log.error("Failed to fetch Amazon [%s]: %s", category, e)

        # Be polite — vary the delay slightly
        time.sleep(AMAZON_REQUEST_DELAY + random.uniform(0, 1.5))

    log.info("Amazon total: %d unique products across %d categories",
             len(all_products), len(AMAZON_CATEGORIES))
    return all_products


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_amazon_bestsellers()
    for p in results[:5]:
        print(f"#{p['rank']} [{p['category']}] {p['title']} — {p['price']}")
