"""
Content Creation Pipeline Entry Point
Runs Phases 1 through 4 sequentially to generate TikTok videos for dropshipping products.
"""

import logging
import time

from phase1_source import run_phase1
from phase2_writer import run_phase2
from phase3_video import run_phase3
from phase4_queue import run_phase4

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    log = logging.getLogger("main_content")
    
    log.info("════════════════════════════════════════════════════════════")
    log.info("Content Pipeline starting (Phases 1-4)")
    log.info("════════════════════════════════════════════════════════════")
    
    start_time = time.time()
    
    # Phase 1: Download assets
    products = run_phase1()
    if not products:
        log.info("No products to process today. Exiting.")
        return
        
    # Phase 2: Generate scripts using Gemini
    run_phase2()
    
    # Phase 3: Stitch videos
    run_phase3()
    
    # Phase 4: Upload to Drive and Queue
    run_phase4()
    
    elapsed = time.time() - start_time
    log.info("════════════════════════════════════════════════════════════")
    log.info("Content Pipeline complete in %ds", int(elapsed))
    log.info("════════════════════════════════════════════════════════════")

if __name__ == "__main__":
    main()
