"""
Phase 4 — Completion logger
Reads Phase 2 output and marks Content_Queue rows as actionable.
Logs a summary so the operator knows what to film today.
"""

import json
import logging
import os
from datetime import datetime

log = logging.getLogger(__name__)


def run_phase4():
    log.info("Phase 4: Completion summary")

    if not os.path.exists("data/phase2_payload.json"):
        log.warning("data/phase2_payload.json not found — Phase 2 may not have run")
        return

    with open("data/phase2_payload.json", "r", encoding="utf-8") as f:
        products = json.load(f)

    if not products:
        log.info("No products in payload")
        return

    log.info("=" * 60)
    log.info("TODAY'S FILMING BRIEFING — %s", datetime.utcnow().strftime("%Y-%m-%d"))
    log.info("=" * 60)
    log.info("Open your Content_Queue sheet to see full scripts.")
    log.info("")

    for p in products:
        script = p.get("script", {})
        log.info("PRODUCT #%s: %s", p.get("rank", "?"), p.get("title", "")[:60])
        log.info("  Hook:   %s", p.get("hook_idea", ""))
        log.info("  Script: %s", script.get("voiceover", "")[:100])
        log.info("  Shots:  %s", script.get("visual_direction", "")[:120])
        log.info("  Tags:   %s", script.get("hashtags", ""))
        log.info("")

    log.info("HOW TO MAKE THE VIDEO (10 minutes):")
    log.info("  Option A — CapCut: Open app > Script to Video > paste voiceover > generate")
    log.info("  Option B — Meta AI: meta.ai/imagine > describe product scene > generate video")
    log.info("  Option C — Film it yourself following the visual direction above")
    log.info("")
    log.info("Once the video is ready, drop it in your Google Drive folder.")
    log.info("n8n will pick it up and post it automatically on schedule.")
    log.info("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    run_phase4()
