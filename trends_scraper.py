"""
Phase 0 — Google Trends signal
Uses pytrends (unofficial Google Trends API wrapper — free, no key needed).
For each product title, returns a score 0–100 representing search interest
over the last 7 days. Higher = more trending right now.
"""

import time
import logging
from pytrends.request import TrendReq
from config import TRENDS_TIMEFRAME, TRENDS_GEO

log = logging.getLogger(__name__)

# pytrends works in batches of 5 keywords max
BATCH_SIZE = 5
DELAY_BETWEEN_BATCHES = 5   # seconds — Google rate-limits aggressively


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
    for i in range(0, len(keywords), BATCH_SIZE):
        batch = keywords[i : i + BATCH_SIZE]
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
                continue

            # Average interest over the period, normalize to 0–1
            for kw in batch:
                if kw in data.columns:
                    avg = data[kw].mean()
                    scores[keyword_map[kw]] = round(float(avg) / 100.0, 4)
                else:
                    scores[keyword_map[kw]] = 0.0

            log.info("Trends batch %d/%d done", i // BATCH_SIZE + 1,
                     -(-len(keywords) // BATCH_SIZE))

        except Exception as e:
            log.error("Trends error on batch %s: %s", batch, e)
            for kw in batch:
                scores[keyword_map[kw]] = 0.0

        time.sleep(DELAY_BETWEEN_BATCHES)

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
