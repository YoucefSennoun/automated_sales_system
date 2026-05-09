"""
Phase 0 — Gemini filter
Sends top products to Gemini 2.5 Flash for quality filtering.
Rejects branded, commodity, and non-dropshippable items.
"""

import json
import logging
import re
import requests
from config import GEMINI_API_URL, GEMINI_API_KEY, SHORTLIST_SIZE

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a dropshipping product expert. Review this product list.

REJECT a product if ANY of these are true:
- It has a specific brand name in the title (TERRO, Amazon Basics, Purina, Nike,
  Apple, Samsung, Owala, BIODANCE, Fancy Feast, PartyWoo, upsimples, or any
  other identifiable brand). Generic category names like "Electric Massager" are
  fine; branded names like "Homedics Massager" are not.
- It is a consumable that needs repeat purchase (food, cleaning supplies, bait stations)
- It is a commodity with zero differentiation (balloons, pee pads, picture frames)
- Price is under $12 or over $70
- It has no clear 15-second video demonstration potential

APPROVE a product only if ALL of these are true:
- It is a generic unbranded or white-label type product
- It solves a visible, relatable everyday problem
- Showing it in action for 15 seconds creates a clear "wow" or "I need that" reaction
- It fits impulse buy psychology ($15-$60 range)
- It is something you could source from AliExpress without infringing any trademark

For approved products, write a HOOK IDEA that:
- Opens with a situation the viewer recognises ("POV:", "Nobody told me about", "This changed how I")
- Does NOT mention any health claims, medical conditions, or body parts clinically
- Is under 12 words
- Sounds like a real person, not an advertisement

Respond ONLY with valid JSON. No markdown. No explanation. Just the JSON object:
{
  "approved": [
    {"id": "0", "reason": "max 8 words why dropshippable", "hook_idea": "hook under 12 words"}
  ],
  "rejected": [
    {"id": "0", "reason": "max 8 words why rejected"}
  ]
}"""


def _sanitize(title: str) -> str:
    """Remove characters that break Gemini JSON output."""
    clean = title.replace('"', "'").replace('\\', '').replace('\n', ' ')
    clean = re.sub(r'[^\x20-\x7E]', '', clean)
    return clean[:50].strip()


def gemini_filter(products: list[dict], top_n: int = SHORTLIST_SIZE * 2) -> list[dict]:
    """Filter products via Gemini. Falls back to top scored if API fails."""
    if not products:
        return []

    if not GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY not set — skipping Gemini filter")
        return sorted(products, key=lambda x: x.get("combined_score", 0), reverse=True)[:SHORTLIST_SIZE]

    candidates = products[:top_n]

    product_list = [
        {
            "id":    str(i),
            "title": _sanitize(p["title"]),
            "price": p.get("price", "N/A"),
        }
        for i, p in enumerate(candidates)
    ]

    payload = {
        "contents": [{"parts": [{"text": SYSTEM_PROMPT + f"\n\nProducts:\n{json.dumps(product_list, ensure_ascii=True)}"}]}],
        "generationConfig": {
            "temperature":      0.1,
            "maxOutputTokens":  1024,
            "responseMimeType": "application/json",
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }

    raw_text = ""
    try:
        resp = requests.post(GEMINI_API_URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        candidate_resp = data["candidates"][0]
        if candidate_resp.get("finishReason") == "MAX_TOKENS":
            log.warning("Gemini hit MAX_TOKENS — using top scored fallback")
            return candidates[:SHORTLIST_SIZE]

        raw_text = candidate_resp["content"]["parts"][0]["text"]
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```", 2)[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("`").strip()

        result = json.loads(clean)

        approved_ids, hook_map, reason_map = set(), {}, {}
        for item in result.get("approved", []):
            try:
                idx = int(item["id"])
                approved_ids.add(idx)
                hook_map[idx]   = item.get("hook_idea", "")
                reason_map[idx] = item.get("reason", "")
            except (KeyError, ValueError):
                continue

        for r in result.get("rejected", []):
            log.info("Gemini rejected #%s: %s", r.get("id","?"), r.get("reason",""))

        filtered = []
        for i, p in enumerate(candidates):
            if i in approved_ids:
                p["hook_idea"]     = hook_map.get(i, "")
                p["gemini_reason"] = reason_map.get(i, "")
                filtered.append(p)

        filtered.sort(key=lambda x: x["combined_score"], reverse=True)
        final = filtered[:SHORTLIST_SIZE]
        log.info("Gemini approved %d/%d products", len(final), len(candidates))
        return final if final else candidates[:SHORTLIST_SIZE]

    except json.JSONDecodeError as e:
        log.error("Gemini invalid JSON: %s | Raw: %s", e, raw_text[:300])
        return candidates[:SHORTLIST_SIZE]
    except Exception as e:
        log.error("Gemini API error: %s", e)
        return candidates[:SHORTLIST_SIZE]