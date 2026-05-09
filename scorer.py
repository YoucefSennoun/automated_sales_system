"""
Phase 0 — Scorer
Combines Amazon rank, Google Trends score, and TikTok score
into a single weighted score for each product.

Key fix: when Trends or TikTok are skipped, weights are redistributed
so scores aren't artificially capped at 0.45.
"""

import logging
from config import (
    SCORE_WEIGHT_AMAZON,
    SCORE_WEIGHT_TRENDS,
    SCORE_WEIGHT_TIKTOK,
    MIN_SCORE_THRESHOLD,
    AMAZON_TOP_N,
    SKIP_TRENDS,
    SKIP_TIKTOK,
)

log = logging.getLogger(__name__)


def _get_weights() -> tuple[float, float, float]:
    """
    Return actual weights based on which signals are active.
    Redistributes weight from skipped signals to Amazon so scores
    stay in the 0–1 range regardless of what's enabled.
    """
    w_amazon = SCORE_WEIGHT_AMAZON
    w_trends = 0.0 if SKIP_TRENDS else SCORE_WEIGHT_TRENDS
    w_tiktok = 0.0 if SKIP_TIKTOK else SCORE_WEIGHT_TIKTOK

    total = w_amazon + w_trends + w_tiktok
    if total == 0:
        return 1.0, 0.0, 0.0

    # Normalize so weights always sum to 1.0
    return w_amazon / total, w_trends / total, w_tiktok / total


def _amazon_rank_to_score(rank: int, max_rank: int = AMAZON_TOP_N) -> float:
    """Rank 1 → 1.0, rank N → near 0. Linear decay."""
    if rank <= 0:
        return 0.0
    score = (max_rank - rank + 1) / max_rank
    return max(0.0, min(1.0, score))


def score_products(
    products:      list[dict],
    trends_scores: dict[str, float],
    tiktok_scores: dict[str, float],
) -> list[dict]:
    """
    Score and rank all products. Returns sorted list (best first).
    Skipped signals contribute 0 and weights are redistributed automatically.
    """
    w_amazon, w_trends, w_tiktok = _get_weights()
    log.info(
        "Scoring weights — Amazon: %.0f%% | Trends: %.0f%% | TikTok: %.0f%%",
        w_amazon * 100, w_trends * 100, w_tiktok * 100,
    )

    # Deduplicate by title before scoring
    seen, unique = set(), []
    for p in products:
        key = p["title"].lower()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    if len(unique) < len(products):
        log.info("Deduplication removed %d duplicate products", len(products) - len(unique))

    scored = []
    for p in unique:
        title        = p["title"]
        amazon_score = _amazon_rank_to_score(p.get("rank", AMAZON_TOP_N))
        trends_score = trends_scores.get(title, 0.0)
        tiktok_score = tiktok_scores.get(title, 0.0)

        combined = (
            amazon_score * w_amazon +
            trends_score * w_trends +
            tiktok_score * w_tiktok
        )

        p["amazon_score"]   = round(amazon_score, 3)
        p["trends_score"]   = round(trends_score, 3)
        p["tiktok_score"]   = round(tiktok_score, 3)
        p["combined_score"] = round(combined, 3)

        if combined >= MIN_SCORE_THRESHOLD:
            scored.append(p)
        else:
            log.debug("Dropped (%.3f < %.2f): %s", combined, MIN_SCORE_THRESHOLD, title)

    scored.sort(key=lambda x: x["combined_score"], reverse=True)
    log.info("Scorer: %d products passed threshold (from %d unique)", len(scored), len(unique))
    return scored


def print_leaderboard(products: list[dict], top_n: int = 10) -> None:
    print(f"\n{'RANK':<5} {'SCORE':<7} {'AMZ':<6} {'TRD':<6} {'TTK':<6} TITLE")
    print("─" * 72)
    for i, p in enumerate(products[:top_n], 1):
        print(
            f"#{i:<4} "
            f"{p['combined_score']:<7.3f} "
            f"{p['amazon_score']:<6.2f} "
            f"{p['trends_score']:<6.2f} "
            f"{p['tiktok_score']:<6.2f} "
            f"{p['title'][:46]}"
        )
    print()