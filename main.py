"""
Phase 0 — Main orchestrator
Runs the full research pipeline in order:
  1. Scrape Amazon best sellers
  2. Score with Google Trends + TikTok signal
  3. Filter to PlusBase store products
  4. Gemini AI sanity check
  5. Write shortlist to Google Sheet

Run: python main.py
Or triggered by GitHub Actions on a schedule.
"""

import logging
import sys
from datetime import datetime

from amazon_scraper   import scrape_amazon_bestsellers
from trends_scraper   import get_trends_scores
from tiktok_signal    import get_tiktok_scores
from scorer           import score_products, print_leaderboard
from plusbase_matcher import filter_to_store_products
from gemini_filter    import gemini_filter
from sheets_output    import write_shortlist
from config           import SKIP_TRENDS, SKIP_TIKTOK, SKIP_PLUSBASE

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"phase0_{datetime.utcnow().strftime('%Y%m%d')}.log"),
    ]
)
log = logging.getLogger("main")


def run():
    start = datetime.utcnow()
    log.info("═" * 60)
    log.info("Phase 0 starting — %s UTC", start.strftime("%Y-%m-%d %H:%M"))
    log.info("═" * 60)

    # ── Step 1: Amazon ───────────────────────────────────────────────────────
    log.info("Step 1/5 — Scraping Amazon best sellers...")
    products = scrape_amazon_bestsellers()

    if not products:
        log.error("No products scraped from Amazon. Exiting.")
        sys.exit(1)

    log.info("  → %d products collected", len(products))

    # ── Step 2: Trend signals ─────────────────────────────────────────────────
    log.info("Step 2/5 — Fetching trend signals...")

    if not SKIP_TRENDS:
        log.info("  → Google Trends...")
        trends_scores = get_trends_scores(products)
    else:
        log.info("  → Google Trends... (SKIPPED in config)")
        trends_scores = {}

    if not SKIP_TIKTOK:
        log.info("  → TikTok presence...")
        tiktok_scores = get_tiktok_scores(products)
    else:
        log.info("  → TikTok presence... (SKIPPED in config)")
        tiktok_scores = {}

    # ── Step 3: Score and rank ────────────────────────────────────────────────
    log.info("Step 3/5 — Scoring and ranking...")
    scored = score_products(products, trends_scores, tiktok_scores)

    if not scored:
        log.error("No products passed the scoring threshold. Exiting.")
        sys.exit(1)

    print_leaderboard(scored, top_n=10)

    # ── Step 4: PlusBase filter ───────────────────────────────────────────────
    log.info("Step 4/5 — Filtering to PlusBase catalog...")
    if not SKIP_PLUSBASE:
        matched = filter_to_store_products(scored)

        if not matched:
            log.warning("No products matched the store catalog. Using top scored products.")
            matched = scored  # fallback: proceed without store filter
    else:
        log.info("  → PlusBase catalog filter... (SKIPPED in config)")
        matched = scored

    log.info("  → %d products after store filter", len(matched))

    # ── Step 5: Gemini filter ─────────────────────────────────────────────────
    log.info("Step 5a/5 — Gemini AI sanity check...")
    final = gemini_filter(matched)

    if not final:
        log.warning("Gemini rejected everything. Using top 5 matched products.")
        final = matched[:5]

    # ── Output ────────────────────────────────────────────────────────────────
    log.info("Step 5b/5 — Writing shortlist to Google Sheet...")
    success = write_shortlist(final)

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = (datetime.utcnow() - start).seconds
    log.info("═" * 60)
    log.info("Phase 0 complete in %ds", elapsed)
    log.info("Today's shortlist (%d products):", len(final))
    for i, p in enumerate(final, 1):
        log.info("  #%d %.2f  %s", i, p["combined_score"], p["title"])
        if p.get("hook_idea"):
            log.info("       Hook: %s", p["hook_idea"])
    log.info("Sheet write: %s", "OK" if success else "FAILED (check logs)")
    log.info("═" * 60)

    # Exit with error if sheet write failed (GitHub Actions will flag it)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    run()
