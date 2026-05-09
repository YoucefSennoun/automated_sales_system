"""
Phase 0 — PlusBase catalog matcher
Checks whether a trending product actually exists in your PlusBase store
so you don't create content for something you can't sell.

How it works:
- Fetches your store's product list via PlusBase's Shopify-compatible JSON endpoint
- Uses fuzzy string matching to compare Amazon product titles to store products
- Returns only products that have a match above the confidence threshold
"""

import logging
import requests
from difflib import SequenceMatcher
from config import PLUSBASE_STORE_URL, USER_AGENTS
import random

log = logging.getLogger(__name__)

# Match confidence 0–1. Below this → product not in store → dropped.
MATCH_THRESHOLD = 0.45

# PlusBase stores use Shopify's product JSON endpoint
PRODUCTS_JSON_URL = "{store}/products.json?limit=250"


def _fetch_store_products(store_url: str) -> list[dict]:
    """
    Fetch all products from your PlusBase store via Shopify's /products.json.
    This endpoint is public on all Shopify/PlusBase stores by default.
    """
    url = PRODUCTS_JSON_URL.format(store=store_url.rstrip("/"))
    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        products = data.get("products", [])
        log.info("PlusBase store: fetched %d products", len(products))
        return products
    except Exception as e:
        log.error("Failed to fetch PlusBase products: %s", e)
        return []


def _similarity(a: str, b: str) -> float:
    """Simple fuzzy match score between two strings."""
    a, b = a.lower(), b.lower()
    return SequenceMatcher(None, a, b).ratio()


def _keyword_overlap(amazon_title: str, store_title: str) -> float:
    """
    Keyword-based overlap: what fraction of Amazon title words
    appear in the store product title?
    Catches cases where titles differ but refer to same product.
    """
    stop = {"with", "and", "for", "the", "a", "an", "in", "of", "to", "&", "-", "set"}
    amazon_words = set(amazon_title.lower().split()) - stop
    store_words  = set(store_title.lower().split()) - stop

    if not amazon_words:
        return 0.0

    overlap = amazon_words & store_words
    return len(overlap) / len(amazon_words)


def _best_match(amazon_title: str, store_products: list[dict]) -> tuple[float, str]:
    """
    Find the best matching store product for an Amazon title.
    Returns (best_score, matched_store_title).
    """
    best_score = 0.0
    best_title = ""

    for sp in store_products:
        store_title = sp.get("title", "")
        if not store_title:
            continue

        # Combine fuzzy match and keyword overlap for a stronger signal
        fuzzy   = _similarity(amazon_title, store_title)
        keyword = _keyword_overlap(amazon_title, store_title)
        score   = (fuzzy * 0.5) + (keyword * 0.5)

        if score > best_score:
            best_score = score
            best_title = store_title

    return best_score, best_title


def filter_to_store_products(
    scored_products: list[dict],
    store_url: str = PLUSBASE_STORE_URL,
) -> list[dict]:
    """
    Filter scored products to only those available in the PlusBase store.
    Adds 'store_match' and 'store_match_score' fields to matching products.
    """
    if not store_url:
        log.warning("PLUSBASE_STORE_URL not set — skipping catalog filter")
        # Return all products unfiltered if store URL not configured
        for p in scored_products:
            p["store_match"]       = "unknown"
            p["store_match_score"] = 0.0
        return scored_products

    # Basic validation of the store URL
    if not (store_url.startswith("http://") or store_url.startswith("https://")):
        log.warning("PLUSBASE_STORE_URL appears malformed (%s) — skipping catalog filter", store_url)
        for p in scored_products:
            p["store_match"]       = "unknown"
            p["store_match_score"] = 0.0
        return scored_products

    store_products = _fetch_store_products(store_url)
    if not store_products:
        log.warning("Could not fetch store products — returning all candidates")
        return scored_products

    matched = []
    for p in scored_products:
        score, match_title = _best_match(p["title"], store_products)

        if score >= MATCH_THRESHOLD:
            p["store_match"]       = match_title
            p["store_match_score"] = round(score, 3)
            matched.append(p)
            log.debug("MATCH [%.2f]: '%s' → '%s'", score, p["title"][:40], match_title[:40])
        else:
            log.debug("NO MATCH [%.2f]: '%s'", score, p["title"][:40])

    log.info("PlusBase filter: %d/%d products matched store catalog",
             len(matched), len(scored_products))
    return matched


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test with mock data (set your store URL in config or env)
    sample = [
        {"title": "Electric Neck Massager",  "combined_score": 0.75},
        {"title": "LED Strip Lights Kit",    "combined_score": 0.68},
        {"title": "Random Product Not In Store", "combined_score": 0.60},
    ]
    results = filter_to_store_products(sample)
    for p in results:
        print(f"[{p['store_match_score']:.2f}] {p['title']} → {p.get('store_match','?')}")
