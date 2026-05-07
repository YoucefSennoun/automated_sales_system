"""
Phase 0 — TikTok signal estimator
No TikTok API needed. We estimate TikTok presence by counting
Google search results for: site:tiktok.com "<product keyword>"
More results = more TikTok content = more viral potential.

Why not scrape TikTok directly?
- TikTok requires auth for most endpoints
- Their JS-heavy pages are hard to scrape reliably
- This Google proxy method is stable, free, and good enough for ranking
"""

import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from config import TIKTOK_SEARCH_DELAY, USER_AGENTS

log = logging.getLogger(__name__)

# Google returns result count in a span — we parse the number from it
GOOGLE_SEARCH_URL = "https://www.google.com/search"

# Result count thresholds → normalized score
# These are approximate — tune after a few runs
THRESHOLDS = [
    (5_000_000, 1.00),
    (1_000_000, 0.85),
    (500_000,   0.70),
    (100_000,   0.50),
    (50_000,    0.35),
    (10_000,    0.20),
    (0,         0.05),
]


def _normalize_count(count: int) -> float:
    for threshold, score in THRESHOLDS:
        if count >= threshold:
            return score
    return 0.0


def _search_tiktok_presence(keyword: str) -> float:
    """
    Search Google for site:tiktok.com "<keyword>" and
    return a normalized score 0.0–1.0.
    """
    query = f'site:tiktok.com "{keyword}"'
    params = {"q": query, "num": 10}
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
    }

    max_retries = 3
    backoff = 15  # seconds — generous initial wait before retrying a 429
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(
                GOOGLE_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 429:
                log.warning("Google rate-limited TikTok search for [%s] – attempt %d", keyword, attempt)
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                return -1.0  # sentinel: all retries exhausted on 429
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            stats_div = soup.find("div", id="result-stats")
            if not stats_div:
                return 0.0
            text = stats_div.get_text()
            import re
            match = re.search(r"[\d,]+", text)
            if not match:
                return 0.0
            count = int(match.group().replace(",", ""))
            score = _normalize_count(count)
            log.debug("TikTok [%s]: ~%d results → score %.2f", keyword, count, score)
            return score
        except Exception as e:
            log.error("TikTok search failed for [%s] on attempt %d: %s", keyword, attempt, e)
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return 0.0


def get_tiktok_scores(products: list[dict]) -> dict[str, float]:
    """
    Returns {product_title: tiktok_score} for all products.
    Adds a small random delay between searches to avoid Google blocks.
    Bails out early if Google is rate-limiting the whole IP session.
    """
    # After this many consecutive products all fail every retry, assume
    # Google has blocked the IP entirely and skip the rest.
    CONSECUTIVE_FAIL_LIMIT = 3
    consecutive_failures = 0

    scores = {}
    for p in products:
        title = p["title"]
        # Use a short 2-3 word version for TikTok search
        keyword = " ".join(title.split()[:3])
        result = _search_tiktok_presence(keyword)

        if result < 0:
            # -1.0 sentinel: all retries exhausted with 429
            scores[title] = 0.0
            consecutive_failures += 1
            if consecutive_failures >= CONSECUTIVE_FAIL_LIMIT:
                log.warning(
                    "TikTok: %d consecutive 429 failures — Google is rate-limiting "
                    "this IP. Skipping remaining %d products (scores default to 0.0).",
                    consecutive_failures,
                    sum(1 for q in products if q["title"] not in scores) - 1,
                )
                # Zero-fill all remaining products
                for remaining in products:
                    if remaining["title"] not in scores:
                        scores[remaining["title"]] = 0.0
                break
        else:
            scores[title] = result
            consecutive_failures = 0  # reset on any success

        time.sleep(TIKTOK_SEARCH_DELAY + random.uniform(0, 1.0))

    return scores


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample = [
        {"title": "Portable Neck Massager"},
        {"title": "Stanley Cup Water Bottle"},
        {"title": "LED Strip Lights for Room"},
    ]
    result = get_tiktok_scores(sample)
    for title, score in result.items():
        print(f"{score:.2f}  {title}")
