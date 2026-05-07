"""
Phase 0 — Google Trends signal
Uses pytrends (unofficial Google Trends API wrapper — free, no key needed).
For each product title, returns a score 0–100 representing search interest
over the last 7 days. Higher = more trending right now.
"""

import time
import random
import logging
from pytrends.request import TrendReq
from config import TRENDS_TIMEFRAME, TRENDS_GEO

log = logging.getLogger(__name__)

# pytrends works in batches of 5 keywords max
BATCH_SIZE = 5
DELAY_BETWEEN_BATCHES = 15   # seconds between batches — respects Google rate limits
MAX_RETRIES = 3              # retries per batch on 429
BACKOFF_BASE = 30            # seconds for first retry (doubles each attempt)


def _extract_keyword(title: str) -> str:
    """
    Shorten a product title to a 2-4 word search keyword.
    pytrends works better with short, specific keywords.
    Example: "Portable Electric Neck & Shoulder Massager with Heat" → "neck massager"
    """
    # Strip common filler words and take first 4 meaningful words
    stop = {"with", "and", "for", "the", "a", "an", "in", "of", "to", "&", "-"}
    words = [w for w in title.split() if w.lower() not in stop]
    return " ".join(words[:3]).lower()


def get_trends_scores(products: list[dict]) -> dict[str, float]:
    """
    Given a list of product dicts (must have 'title' key),
    returns {title: trend_score} where score is 0.0–1.0.
    """
    pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))

    # Map shortened keyword → original title(s)
    keyword_map: dict[str, str] = {}
    for p in products:
        kw = _extract_keyword(p["title"])
        # Avoid duplicate keywords mapping to same slot
        if kw not in keyword_map:
            keyword_map[kw] = p["title"]

    keywords = list(keyword_map.keys())
    scores: dict[str, float] = {}

    # Process in batches of BATCH_SIZE
    total_batches = -(-len(keywords) // BATCH_SIZE)
    for i in range(0, len(keywords), BATCH_SIZE):
        batch = keywords[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        success = False
        backoff = BACKOFF_BASE
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                pytrends.build_payload(
                    batch,
                    timeframe=TRENDS_TIMEFRAME,
                    geo=TRENDS_GEO,
                )
                data = pytrends.interest_over_time()

                if data.empty:
                    for kw in batch:
                        scores[keyword_map[kw]] = 0.0
                else:
                    # Average interest over the period, normalize to 0–1
                    for kw in batch:
                        if kw in data.columns:
                            avg = data[kw].mean()
                            scores[keyword_map[kw]] = round(float(avg) / 100.0, 4)
                        else:
                            scores[keyword_map[kw]] = 0.0

                log.info("Trends batch %d/%d done", batch_num, total_batches)
                success = True
                break  # done — exit retry loop

            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "rate" in err_str.lower()
                if is_rate_limit and attempt < MAX_RETRIES:
                    jitter = random.uniform(0, 10)
                    wait = backoff + jitter
                    log.warning(
                        "Trends 429 on batch %d/%d (attempt %d/%d) — waiting %.0fs",
                        batch_num, total_batches, attempt, MAX_RETRIES, wait
                    )
                    time.sleep(wait)
                    backoff *= 2
                else:
                    log.error("Trends error on batch %s (attempt %d): %s", batch, attempt, e)
                    for kw in batch:
                        scores[keyword_map[kw]] = 0.0
                    break  # give up on this batch

        time.sleep(DELAY_BETWEEN_BATCHES + random.uniform(0, 3))

    return scores


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample = [
        {"title": "Portable Neck Massager with Heat"},
        {"title": "Silicone Kitchen Utensil Set"},
        {"title": "LED Plant Grow Light"},
    ]
    result = get_trends_scores(sample)
    for title, score in result.items():
        print(f"{score:.2f}  {title}")
