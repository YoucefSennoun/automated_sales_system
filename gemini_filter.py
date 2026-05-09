"""
Phase 0 — Gemini filter
Fix: sanitize titles before sending (removes rogue quotes/pipes),
increase maxOutputTokens, reduce batch size to avoid truncation.
"""

import json
import logging
import re
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
- Has a wow factor or surprising result

For HOOK IDEAS rules:
- Write lifestyle or curiosity hooks ONLY
- NEVER mention pain, medical conditions, treatment, cures, or health benefits
- NEVER mention body parts in a clinical way
- Keep hooks fun, surprising, or relatable — max 15 words

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


def _sanitize_title(title: str) -> str:
    """
    Remove characters that break JSON when Gemini echoes them back.
    Truncate to 60 chars to keep token count manageable.
    """
    clean = title.replace('"', "'").replace('\\', '')
    clean = re.sub(r'[^\x20-\x7E]', '', clean)   # strip non-ASCII
    return clean[:60].strip()


def gemini_filter(products: list[dict], top_n: int = SHORTLIST_SIZE * 2) -> list[dict]:
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
            "title":    _sanitize_title(p["title"]),   # sanitized — no rogue quotes
            "category": p.get("category", "unknown"),
            "price":    p.get("price", "N/A"),
        }
        for i, p in enumerate(candidates)
    ]

    payload = {
        "contents": [{
            "parts": [{
                "text": SYSTEM_PROMPT + f"\n\nProduct list:\n{json.dumps(product_list, indent=2, ensure_ascii=True)}"
            }]
        }],
        "generationConfig": {
            "temperature":      0.2,
            "maxOutputTokens":  4096,        # was 2048 — increased to avoid truncation
            "responseMimeType": "application/json",
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    raw_text = ""
    try:
        resp = requests.post(GEMINI_API_URL, json=payload, timeout=60)
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

        try:
            result = json.loads(clean)
        except json.JSONDecodeError as e:
            log.warning("Gemini returned invalid JSON. Attempting regex fallback... Error: %s", e)
            result = {"approved": [], "rejected": []}
            for block in re.finditer(r'\{([^{}]*)\}', clean):
                inner = block.group(1)
                if '"id"' in inner and '"hook_idea"' in inner:
                    id_match = re.search(r'"id"\s*:\s*"(\d+)"', inner)
                    reason_match = re.search(r'"reason"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', inner)
                    hook_match = re.search(r'"hook_idea"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', inner)
                    if id_match:
                        result["approved"].append({
                            "id": id_match.group(1),
                            "reason": reason_match.group(1).replace('\\"', '"') if reason_match else "",
                            "hook_idea": hook_match.group(1).replace('\\"', '"') if hook_match else ""
                        })
            if not result["approved"]:
                raise  # Re-raise to trigger the outer except block

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
            log.error("Raw (first 400 chars): %s", raw_text[:400])
        return candidates[:SHORTLIST_SIZE]

    except Exception as e:
        log.error("Gemini API error: %s", e)
        return candidates[:SHORTLIST_SIZE]