"""
Phase 2 — Script & Briefing Generator
Reads today's approved products from the Phase 0 Google Sheet.
Uses Gemini to write a complete TikTok video script for each product.
Writes a human-readable briefing to the Content_Queue sheet so the
operator knows exactly what video to make in CapCut or Meta AI.
"""

import json
import logging
import os
import re
import time
import requests
from datetime import datetime
from config import GEMINI_PHASE2_URL, GEMINI_API_KEY, GSHEET_SPREADSHEET_ID, GSHEET_WORKSHEET_NAME
from sheets_output import _get_client

log = logging.getLogger(__name__)

SCRIPT_PROMPT = """You are a viral TikTok content writer for a dropshipping store.

Write a complete 15-20 second TikTok video script for this product.

Rules:
- Voiceover must be 40-55 words. Conversational tone, not an ad.
- Start with the hook provided. Make it sound like a real person's discovery.
- Captions: 4-5 short phrases (1-4 words each) timed to the voiceover beats.
- Hashtags: 5 hashtags. Mix niche (#homedecor) and viral (#tiktokmademebuyit).
- Visual direction: 3-4 simple shot descriptions for a non-professional filming
  with their phone. Example: "Close-up of product from box. Hands using it.
  Before/after reaction shot."
- Do NOT mention price. Do NOT say "link in bio" in the voiceover (it sounds fake).

Respond with valid JSON only:
{
  "voiceover": "full script text here",
  "captions": ["Hook phrase", "Key benefit", "Reaction", "CTA"],
  "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5",
  "visual_direction": "Shot 1: ... Shot 2: ... Shot 3: ..."
}"""


def generate_script(product: dict) -> dict:
    """Generate TikTok script via Gemini with retry."""
    if not GEMINI_API_KEY:
        return {}

    prompt = (
        f"Product: {product['title']}\n"
        f"Hook to use: {product.get('hook_idea', 'You need to see this')}\n"
        f"Why it works: {product.get('gemini_reason', '')}\n"
        f"Price: {product.get('price', '')}"
    )

    payload = {
        "contents": [{"parts": [{"text": SCRIPT_PROMPT + "\n\n" + prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024, "responseMimeType": "application/json"},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }

    for attempt in range(3):
        try:
            resp = requests.post(GEMINI_PHASE2_URL, json=payload, timeout=60)
            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                log.warning("Rate limited, waiting %ds (attempt %d/3)", wait, attempt + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip().rstrip("`").strip())
        except Exception as e:
            log.warning("Script generation attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(15)

    return {}


def run_phase2() -> list[dict]:
    """Read today's products, generate scripts, write briefings to Content_Queue."""
    log.info("Phase 2: Script generation starting")

    today = datetime.utcnow().strftime("%Y-%m-%d")
    client = _get_client()
    sheet  = client.open_by_key(GSHEET_SPREADSHEET_ID)
    ws     = sheet.worksheet(GSHEET_WORKSHEET_NAME)

    all_rows = ws.get_all_records()
    products = [r for r in all_rows if r.get("date") == today and r.get("status") == "pending"]

    if not products:
        log.info("No pending products for today (%s)", today)
        return []

    log.info("Found %d products to script", len(products))

    # Get or create Content_Queue worksheet
    try:
        queue_ws = sheet.worksheet("Content_Queue")
    except Exception:
        queue_ws = sheet.add_worksheet(title="Content_Queue", rows=1000, cols=8)
        queue_ws.update("A1", [["date", "rank", "product_title", "hook", "voiceover",
                                  "captions", "hashtags", "visual_direction", "status"]])
        log.info("Created Content_Queue worksheet")

    results = []
    for row in products:
        title = row.get("title", "")
        if not title:
            continue

        log.info("Scripting: %s", title[:60])
        script = generate_script(row)

        if not script:
            script = {
                "voiceover": f"{row.get('hook_idea', 'You need to see this')}. "
                             f"I found this and I can't stop using it. Seriously, where has this been all my life.",
                "captions":  ["Wait for it", "Game changer", "I'm obsessed", "Get yours"],
                "hashtags":  "#tiktokmademebuyit #musthave #fyp #productreview #trending",
                "visual_direction": "Shot 1: Unbox product. Shot 2: Use it showing the key benefit. Shot 3: Reaction face showing satisfaction.",
            }

        # Write to Content_Queue
        queue_ws.append_row([
            today,
            row.get("rank", ""),
            title,
            row.get("hook_idea", ""),
            script.get("voiceover", ""),
            " | ".join(script.get("captions", [])),
            script.get("hashtags", ""),
            script.get("visual_direction", ""),
            "ready_to_film",
        ], value_input_option="USER_ENTERED")

        results.append({**row, "script": script})
        log.info("  Script written for rank #%s", row.get("rank"))
        time.sleep(15)   # respect Gemini free tier rate limits

    # Save locally for Phase 4
    os.makedirs("data", exist_ok=True)
    with open("data/phase2_payload.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    log.info("Phase 2 complete — %d scripts written to Content_Queue sheet", len(results))
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    run_phase2()
