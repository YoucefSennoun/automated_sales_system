"""
Phase 0 — Scorer
Combines Amazon rank, Google Trends score, and TikTok score
into a single weighted score for each product.
Also handles deduplication and minimum threshold filtering.
"""

import logging
from config import (
    SCORE_WEIGHT_AMAZON,
    SCORE_WEIGHT_TRENDS,
    SCORE_WEIGHT_TIKTOK,
    MIN_SCORE_THRESHOLD,
    AMAZON_TOP_N,
)

log = logging.getLogger(__name__)


def _amazon_rank_to_score(rank: int, max_rank: int = AMAZON_TOP_N) -> float:
    """
    Convert Amazon rank to a 0–1 score.
    Rank 1 → 1.0, rank 20 → ~0.05. Exponential decay.
    """
    if rank <= 0:
        return 0.0
    # Exponential: score = (max_rank - rank + 1) / max_rank
    score = (max_rank - rank + 1) / max_rank
    return max(0.0, min(1.0, score))


def score_products(
    products:       list[dict],
    trends_scores:  dict[str, float],
    tiktok_scores:  dict[str, float],
) -> list[dict]:
    """
    Attaches scores to each product and returns sorted list (best first).

    Input products must have: title, rank, category, source
    trends_scores:  {title: 0.0–1.0}
    tiktok_scores:  {title: 0.0–1.0}

    Returns list of product dicts with added fields:
        amazon_score, trends_score, tiktok_score, combined_score
    """
    scored = []

    for p in products:
        title = p["title"]

        amazon_score  = _amazon_rank_to_score(p.get("rank", AMAZON_TOP_N))
        trends_score  = trends_scores.get(title, 0.0)
        tiktok_score  = tiktok_scores.get(title, 0.0)

        combined = (
            amazon_score  * SCORE_WEIGHT_AMAZON +
            trends_score  * SCORE_WEIGHT_TRENDS +
            tiktok_score  * SCORE_WEIGHT_TIKTOK
        )

        # Bonus: product appears to be genuinely trending (all signals agree)
        if amazon_score > 0.5 and trends_score > 0.4 and tiktok_score > 0.3:
            combined = min(1.0, combined * 1.15)
            log.debug("Consensus bonus applied to: %s", title)

        p["amazon_score"]   = round(amazon_score, 3)
        p["trends_score"]   = round(trends_score, 3)
        p["tiktok_score"]   = round(tiktok_score, 3)
        p["combined_score"] = round(combined, 3)

        if combined >= MIN_SCORE_THRESHOLD:
            scored.append(p)
        else:
            log.debug("Dropped (below threshold %.2f): %s [%.3f]",
                      MIN_SCORE_THRESHOLD, title, combined)

    # Sort best first
    scored.sort(key=lambda x: x["combined_score"], reverse=True)
    log.info("Scorer: %d products above threshold (from %d total)",
             len(scored), len(products))
    return scored


def print_leaderboard(products: list[dict], top_n: int = 10) -> None:
    """Print a readable leaderboard to stdout."""
    print(f"\n{'RANK':<5} {'SCORE':<7} {'AMZ':<6} {'TRD':<6} {'TTK':<6} TITLE")
    print("─" * 70)
    for i, p in enumerate(products[:top_n], 1):
        print(
            f"#{i:<4} "
            f"{p['combined_score']:<7.3f} "
            f"{p['amazon_score']:<6.2f} "
            f"{p['trends_score']:<6.2f} "
            f"{p['tiktok_score']:<6.2f} "
            f"{p['title'][:45]}"
        )
    print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Quick test with mock data
    sample_products = [
        {"title": "Neck Massager with Heat", "rank": 1,  "category": "health"},
        {"title": "LED Strip Lights",        "rank": 5,  "category": "home"},
        {"title": "Silicone Baking Mat",     "rank": 15, "category": "kitchen"},
    ]
    mock_trends = {
        "Neck Massager with Heat": 0.72,
        "LED Strip Lights":        0.55,
        "Silicone Baking Mat":     0.30,
    }
    mock_tiktok = {
        "Neck Massager with Heat": 0.80,
        "LED Strip Lights":        0.90,
        "Silicone Baking Mat":     0.20,
    }
    results = score_products(sample_products, mock_trends, mock_tiktok)
    print_leaderboard(results)
