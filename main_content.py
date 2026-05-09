"""
Content Pipeline — Phases 2 and 4
Runs after Phase 0 (main.py). Generates scripts from today's product shortlist
and writes a filming briefing to the Content_Queue sheet.
Phase 1 (image scraping) and Phase 3 (video assembly) have been removed.
Videos are now made manually using CapCut or Meta AI in ~10 minutes.
"""

import logging
import sys
import time

from phase2_writer import run_phase2
from phase4_queue  import run_phase4

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    log = logging.getLogger("main_content")

    log.info("Content pipeline starting (Phase 2 + Phase 4)")
    start = time.time()

    products = run_phase2()
    if not products:
        log.info("No products to process today — exiting")
        return

    run_phase4()

    log.info("Content pipeline complete in %ds", int(time.time() - start))


if __name__ == "__main__":
    main()
