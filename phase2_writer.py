"""
Phase 2 — Script Generation
Reads Phase 1 payload and generates a TikTok video script (voiceover, captions, hashtags) 
for each product using Gemini 2.5 Flash.
"""

import json
import logging
import os
import requests
from config import GEMINI_API_URL, GEMINI_API_KEY

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert TikTok dropshipping content creator.
Write a highly engaging, viral 15-30 second TikTok video script for the following product.

We need:
1. voiceover_text: A conversational, fast-paced voiceover script. Start with a strong hook! No robotic corporate language.
2. captions: An array of short, punchy captions to display on screen (1-3 words max per caption, matching the voiceover).
3. hashtags: A string of 3-5 trending, relevant TikTok hashtags.

Rules:
- Make the voiceover sound like a real user reviewing it or discovering a life hack.
- Keep the voiceover short enough for a 15-20 second video (around 40-50 words max).
- Include the hook idea provided.

Respond ONLY with valid JSON:
{
  "voiceover_text": "...",
  "captions": ["Hook caption", "Next point", "Benefit", "Call to action"],
  "hashtags": "#tiktokmademebuyit #musthaves"
}
"""

def generate_script(product: dict) -> dict:
    """Uses Gemini API to generate the script."""
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY not set!")
        return {}

    prompt_text = (
        f"Product Title: {product['title']}\n"
        f"Selling Price: {product['price']}\n"
        f"Hook Idea: {product['hook_idea']}\n"
        f"Reason it's good: {product['gemini_reason']}\n"
    )

    payload = {
        "contents": [{
            "parts": [{"text": SYSTEM_PROMPT + "\n\n" + prompt_text}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    try:
        resp = requests.post(GEMINI_API_URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Clean JSON markdown fences if present
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```", 2)[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("`").strip()
        
        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            log.warning("Gemini returned invalid JSON (possibly truncated). Attempting regex fallback... Error: %s", e)
            import re
            result = {"voiceover_text": "", "captions": [], "hashtags": ""}
            
            vo_match = re.search(r'"voiceover_text"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', clean)
            if vo_match:
                result["voiceover_text"] = vo_match.group(1).replace('\\"', '"')
                
            hash_match = re.search(r'"hashtags"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', clean)
            if hash_match:
                result["hashtags"] = hash_match.group(1).replace('\\"', '"')
                
            cap_match = re.search(r'"captions"\s*:\s*\[(.*?)\]', clean, re.DOTALL)
            if cap_match:
                cap_str = cap_match.group(1)
                captions = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', cap_str)
                result["captions"] = [c.replace('\\"', '"') for c in captions]
                
            if result["voiceover_text"]:
                return result
            else:
                raise
        
    except Exception as e:
        log.error("Gemini script generation failed for %s: %s", product.get("title", "")[:20], e)
        return {}

def run_phase2():
    log.info("Starting Phase 2: Script Generation")
    
    if not os.path.exists("data/phase1_payload.json"):
        log.error("data/phase1_payload.json not found! Run Phase 1 first.")
        return []
        
    with open("data/phase1_payload.json", "r", encoding="utf-8") as f:
        products = json.load(f)
        
    for p in products:
        log.info("Writing script for: %s", p["title"][:50])
        script_data = generate_script(p)
        
        if script_data:
            p["video_script"] = script_data
        else:
            p["video_script"] = {
                "voiceover_text": f"You won't believe what this {p['title'][:20]} does! Link in bio.",
                "captions": ["Omg", "Wait for it", "Link in bio"],
                "hashtags": "#trending"
            }
            
        # Add a 15-second delay to avoid hitting Gemini 2.5 Flash free tier 15 RPM limit
        import time
        time.sleep(15)
            
    with open("data/phase2_payload.json", "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2)
        
    log.info("Phase 2 complete. Payload saved to data/phase2_payload.json")
    return products

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    run_phase2()
