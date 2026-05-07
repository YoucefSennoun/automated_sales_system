"""
Phase 0 — Gemini filter
Sends the shortlist to Gemini 2.5 Flash for a final sanity check.
Gemini removes products that are:
  - Oversaturated (everyone on TikTok already sells this)
  - Restricted/banned on social platforms (e.g. certain health claims)
  - Likely low-margin for dropshipping
  - Seasonal (if it's not the right season)
  - Legally risky (fake brand items, counterfeit risk)

Uses the free Gemini API — 1500 requests/day.
"""

import json
import logging
import requests
from config import GEMINI_API_URL, SHORTLIST_SIZE

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a dropshipping and social media marketing expert.
You will receive a list of trending products. Your job is to filter out bad choices.

Remove a product if ANY of these apply:
1. The market is completely saturated (e.g. fidget spinners in 2023, AirPod cases)
2. The product requires specific health/medical claims that violate ad policies
3. It is clearly a brand-name item that would be a counterfeit if dropshipped
4. It is highly seasonal and the season has passed
5. It has extremely low perceived value for the price typical in dropshipping
6. It is a commodity with no differentiation (plain white t-shirts, generic phone cases)

Keep a product if it has:
- Clear viral potential on TikTok/Instagram
- Solves a visible problem that's easy to demonstrate in a short video
- Works well as impulse buy ($15–$60 range typically)
- Can be demonstrated without professional studio setup

Respond ONLY with a valid JSON object in this exact format, no markdown:
{
  "approved": [
    {
      "title": "exact product title from input",
      "reason": "one sentence why this is a good pick",
      "hook_idea": "one sentence video hook idea for TikTok"
    }
  ],
  "rejected": [
    {
      "title": "exact product title from input",
      "reason": "one sentence why this was removed"
    }
  ]
}
"""


def gemini_filter(products: list[dict], top_n: int = SHORTLIST_SIZE * 2) -> list[dict]:
    """
    Send top_n products to Gemini for filtering.
    Returns approved products with added 'hook_idea' and 'gemini_reason' fields.
    """
    if not products:
        return []

    # Only send top candidates to save API quota
    candidates = products[:top_n]

    # Build simple product list for the prompt
    product_list = [
        {
            "title":    p["title"],
            "category": p.get("category", "unknown"),
            "score":    p.get("combined_score", 0),
            "price":    p.get("price", "N/A"),
        }
        for p in candidates
    ]

    user_message = f"Filter this product list:\n{json.dumps(product_list, indent=2)}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SYSTEM_PROMPT + "\n\n" + user_message}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,    # Low temp = consistent, analytical responses
            "maxOutputTokens": 2048,
        }
    }

    try:
        resp = requests.post(GEMINI_API_URL, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

        # Strip any accidental markdown fences
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("```").strip()

        result = json.loads(clean)
        approved_titles = {item["title"] for item in result.get("approved", [])}

        # Merge Gemini's reasoning back into the product dicts
        hook_map   = {item["title"]: item.get("hook_idea", "") for item in result.get("approved", [])}
        reason_map = {item["title"]: item.get("reason", "")    for item in result.get("approved", [])}

        filtered = []
        for p in candidates:
            if p["title"] in approved_titles:
                p["hook_idea"]      = hook_map.get(p["title"], "")
                p["gemini_reason"]  = reason_map.get(p["title"], "")
                filtered.append(p)

        # Sort by combined_score, return top SHORTLIST_SIZE
        filtered.sort(key=lambda x: x["combined_score"], reverse=True)
        final = filtered[:SHORTLIST_SIZE]

        log.info("Gemini filter: %d approved → returning top %d",
                 len(filtered), len(final))

        # Log rejections for visibility
        for r in result.get("rejected", []):
            log.info("REJECTED by Gemini: %s — %s", r["title"][:50], r["reason"])

        return final

    except json.JSONDecodeError as e:
        log.error("Gemini returned invalid JSON: %s", e)
        log.debug("Raw response: %s", raw_text[:500] if 'raw_text' in dir() else "N/A")
        # Fallback: return top products without Gemini filter
        return candidates[:SHORTLIST_SIZE]

    except Exception as e:
        log.error("Gemini API error: %s", e)
        return candidates[:SHORTLIST_SIZE]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mock = [
        {"title": "Portable Neck Massager", "category": "health",  "combined_score": 0.82, "price": "$29.99"},
        {"title": "LED Strip Lights",       "category": "home",    "combined_score": 0.75, "price": "$19.99"},
        {"title": "Generic Phone Case",     "category": "electronics", "combined_score": 0.60, "price": "$8.99"},
        {"title": "Fidget Spinner",         "category": "toys",    "combined_score": 0.55, "price": "$4.99"},
    ]
    result = gemini_filter(mock)
    print("\nFinal approved products:")
    for p in result:
        print(f"  ✓ {p['title']}")
        print(f"    Hook: {p.get('hook_idea', 'N/A')}")
