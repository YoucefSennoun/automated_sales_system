"""
Phase 0 — Gemini filter
Sends the shortlist to Gemini 2.5 Flash for a final sanity check.
Removes bad product picks and generates TikTok hook ideas.

Fix: prompt explicitly instructs Gemini to avoid health/medical language
in hooks, which was causing safety blocks on the previous version.
"""

import json
import logging
import requests
from config import GEMINI_API_URL, GEMINI_API_KEY, SHORTLIST_SIZE

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a dropshipping and TikTok marketing expert.
Review this product list and decide which are good to sell and promote.

REMOVE a product if it:
- Is a well-known brand that cannot be dropshipped (Nike, Apple, Samsung, etc.)
- Is a commodity with zero differentiation (plain phone cases, basic socks)
- Is completely market-saturated (fidget spinners, pop sockets in 2024)
- Costs under $8 or over $80 (bad margins or hard impulse buy)
- Has no visual demonstration potential for short video

KEEP a product if it:
- Solves a visible everyday problem
- Can be shown working in under 15 seconds of video
- Is in the $12-$60 price range
- Has a "wow factor" or surprising result

For HOOK IDEAS — very important rules:
- Write lifestyle or curiosity hooks ONLY ("I can't believe this works", "Why didn't I know about this sooner")
- NEVER mention pain, medical conditions, treatment, cures, or health benefits
- NEVER mention body parts in a clinical way
- Keep hooks fun, surprising, or relatable

Respond ONLY with valid JSON, no markdown, no extra text:
{
  "approved": [
    {
      "id": "number from input",
      "reason": "one sentence why good for dropshipping",
      "hook_idea": "one sentence lifestyle hook for TikTok"
    }
  ],
  "rejected": [
    {
      "id": "number from input",
      "reason": "one sentence why removed"
    }
  ]
}"""


def gemini_filter(products: list[dict], top_n: int = SHORTLIST_SIZE * 3) -> list[dict]:
    """
    Send top_n products to Gemini for filtering.
    Returns approved products with hook_idea and gemini_reason fields added.
    Falls back gracefully if API key missing or request fails.
    """
    if not products:
        return []

    if not GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY not set — skipping Gemini filter")
        return sorted(products, key=lambda x: x.get("combined_score", 0), reverse=True)[:SHORTLIST_SIZE]

    candidates = products[:top_n]

    product_list = [
        {
            "id":       str(i),
            "title":    p["title"],
            "category": p.get("category", "unknown"),
            "price":    p.get("price", "N/A"),
            "score":    p.get("combined_score", 0),
        }
        for i, p in enumerate(candidates)
    ]

    payload = {
        "contents": [{
            "parts": [{
                "text": SYSTEM_PROMPT + f"\n\nProduct list:\n{json.dumps(product_list, indent=2)}"
            }]
        }],
        "generationConfig": {
            "temperature":      0.2,
            "maxOutputTokens":  2048,
            "responseMimeType": "application/json",
        },
        # Permissive safety — hooks are commercial marketing, not harmful content
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }

    raw_text = ""
    try:
        resp = requests.post(GEMINI_API_URL, json=payload, timeout=45)
        resp.raise_for_status()
        data     = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

        # Strip accidental markdown fences
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```", 2)[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("`").strip()

        result = json.loads(clean)

        approved_ids = set()
        hook_map, reason_map = {}, {}
        for item in result.get("approved", []):
            try:
                idx = int(item["id"])
                approved_ids.add(idx)
                hook_map[idx]   = item.get("hook_idea", "")
                reason_map[idx] = item.get("reason", "")
            except (KeyError, ValueError):
                continue

        filtered = []
        for i, p in enumerate(candidates):
            if i in approved_ids:
                p["hook_idea"]     = hook_map.get(i, "")
                p["gemini_reason"] = reason_map.get(i, "")
                filtered.append(p)

        for r in result.get("rejected", []):
            log.info("Gemini rejected #%s: %s", r.get("id", "?"), r.get("reason", ""))

        filtered.sort(key=lambda x: x["combined_score"], reverse=True)
        final = filtered[:SHORTLIST_SIZE]
        log.info("Gemini: %d approved → returning top %d", len(filtered), len(final))
        return final

    except json.JSONDecodeError as e:
        log.error("Gemini returned invalid JSON: %s", e)
        if raw_text:
            log.error("Raw (first 300 chars): %s", raw_text[:300])
        return candidates[:SHORTLIST_SIZE]

    except Exception as e:
        log.error("Gemini API error: %s", e)
        return candidates[:SHORTLIST_SIZE]