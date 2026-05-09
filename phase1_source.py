"""
Phase 1 — Source & Asset Collection
Reads the Phase 0 Google Sheet for today's shortlisted products.
Downloads high-quality product images to be used in the TikTok video.
"""

import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse
from config import GSHEET_SPREADSHEET_ID, GSHEET_WORKSHEET_NAME
from sheets_output import _get_client, HEADERS

log = logging.getLogger(__name__)

def fetch_product_images(query: str, num_images: int = 3, output_dir: str = "assets") -> list[str]:
    """Scrapes Bing Images to find product images."""
    os.makedirs(output_dir, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }
    url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}"
    
    downloaded_paths = []
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        image_elements = soup.find_all("a", class_="iusc")
        
        count = 0
        for img_tag in image_elements:
            if count >= num_images:
                break
                
            m_data = img_tag.get("m")
            if not m_data:
                continue
                
            try:
                m_json = json.loads(m_data)
                img_url = m_json.get("murl")
                
                if not img_url or not img_url.startswith("http"):
                    continue
                    
                # Download the image
                img_resp = requests.get(img_url, headers=headers, timeout=5)
                if img_resp.status_code == 200:
                    ext = img_url.split(".")[-1][:4].split("?")[0]
                    if ext.lower() not in ["jpg", "jpeg", "png", "webp"]:
                        ext = "jpg"
                        
                    safe_title = "".join(c if c.isalnum() else "_" for c in query[:20])
                    filename = f"{safe_title}_{count}.{ext}"
                    filepath = os.path.join(output_dir, filename)
                    
                    with open(filepath, "wb") as f:
                        f.write(img_resp.content)
                        
                    downloaded_paths.append(filepath)
                    count += 1
            except Exception as e:
                log.debug("Failed to download image: %s", e)
                continue
                
    except Exception as e:
        log.error("Error scraping images for %s: %s", query, e)
        
    return downloaded_paths

def run_phase1() -> list[dict]:
    """Reads today's products from Google Sheet and downloads their images."""
    log.info("Starting Phase 1: Asset Collection")
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    client = _get_client()
    sheet = client.open_by_key(GSHEET_SPREADSHEET_ID)
    ws = sheet.worksheet(GSHEET_WORKSHEET_NAME)
    
    all_rows = ws.get_all_records()
    today_products = [row for row in all_rows if row.get("date") == today and row.get("status") == "pending"]
    
    if not today_products:
        log.info("No pending products found for today (%s)", today)
        return []
        
    log.info("Found %d pending products for %s", len(today_products), today)
    
    payload = []
    
    for row in today_products:
        title = row.get("title", "")
        if not title:
            continue
            
        log.info("Fetching assets for: %s", title[:50])
        # Clean title for better search results
        search_query = title.split("-")[0].split("|")[0].strip() + " product"
        
        image_paths = fetch_product_images(search_query, num_images=3, output_dir=f"assets/{row['rank']}")
        
        product_data = {
            "rank": row.get("rank"),
            "title": title,
            "hook_idea": row.get("hook_idea", ""),
            "gemini_reason": row.get("gemini_reason", ""),
            "price": row.get("price", ""),
            "images": image_paths
        }
        payload.append(product_data)
        
    # Save payload locally to pass to Phase 2
    os.makedirs("data", exist_ok=True)
    with open("data/phase1_payload.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        
    log.info("Phase 1 complete. Payload saved to data/phase1_payload.json")
    return payload

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    run_phase1()
