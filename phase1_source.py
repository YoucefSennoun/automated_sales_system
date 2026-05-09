"""
Phase 1 — Source & Asset Collection
Reads the Phase 0 Google Sheet for today's shortlisted products.
Scrapes product images directly from Amazon product pages (not Bing).
"""

import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from config import GSHEET_SPREADSHEET_ID, GSHEET_WORKSHEET_NAME
from sheets_output import _get_client

log = logging.getLogger(__name__)

HEADERS_REQ = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_amazon_images(amazon_url: str, num_images: int = 3, output_dir: str = "assets") -> list[str]:
    """Scrapes product images directly from the Amazon product page."""
    os.makedirs(output_dir, exist_ok=True)
    downloaded_paths = []
    
    if not amazon_url or "amazon.com" not in amazon_url:
        log.warning("No valid Amazon URL provided")
        return []
    
    try:
        resp = requests.get(amazon_url, headers=HEADERS_REQ, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        image_urls = []
        
        # Method 1: Look for high-res images in the main image block
        main_img = soup.find("img", {"id": "landingImage"})
        if main_img:
            src = main_img.get("data-old-hires") or main_img.get("src")
            if src and src.startswith("http"):
                image_urls.append(src)
        
        # Method 2: Look for thumbnail strip images and get their hi-res versions
        thumb_imgs = soup.find_all("img", class_="a-dynamic-image")
        for img in thumb_imgs:
            src = img.get("data-old-hires") or img.get("src")
            if src and src.startswith("http") and src not in image_urls:
                # Convert thumbnail URL to high-res by replacing size params
                hi_res = src.split("._")[0] + "._AC_SL1500_.jpg" if "._" in src else src
                image_urls.append(hi_res)
                
        # Method 3: Search for any large product images
        all_imgs = soup.find_all("img")
        for img in all_imgs:
            src = img.get("src", "")
            if "images-amazon.com" in src and "product" in src.lower():
                if src not in image_urls:
                    image_urls.append(src)
        
        # Download the images
        count = 0
        for img_url in image_urls:
            if count >= num_images:
                break
            try:
                img_resp = requests.get(img_url, headers=HEADERS_REQ, timeout=5)
                if img_resp.status_code == 200 and len(img_resp.content) > 5000:
                    # Only save images larger than 5KB (skip tiny icons/placeholders)
                    ext = "jpg"
                    filename = f"product_{count}.{ext}"
                    filepath = os.path.join(output_dir, filename)
                    
                    with open(filepath, "wb") as f:
                        f.write(img_resp.content)
                    
                    downloaded_paths.append(filepath)
                    count += 1
                    log.debug("Downloaded image %d: %s", count, img_url[:60])
            except Exception as e:
                log.debug("Failed to download image: %s", e)
                continue
                
    except Exception as e:
        log.warning("Error scraping Amazon images: %s", e)
    
    # Fallback: if Amazon blocked us, try a simple Bing search
    if not downloaded_paths:
        log.warning("Amazon image scrape returned 0 images. Trying Bing fallback...")
        downloaded_paths = _bing_fallback(output_dir, num_images)
    
    return downloaded_paths

def _bing_fallback(output_dir: str, num_images: int, query: str = "") -> list[str]:
    """Last resort: search Bing Images."""
    import urllib.parse
    downloaded = []
    
    if not query:
        return downloaded
        
    try:
        url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query + ' product photo')}"
        resp = requests.get(url, headers=HEADERS_REQ, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        for img_tag in soup.find_all("a", class_="iusc"):
            if len(downloaded) >= num_images:
                break
            m_data = img_tag.get("m")
            if not m_data:
                continue
            try:
                m_json = json.loads(m_data)
                img_url = m_json.get("murl")
                if not img_url:
                    continue
                img_resp = requests.get(img_url, headers=HEADERS_REQ, timeout=5)
                if img_resp.status_code == 200 and len(img_resp.content) > 5000:
                    filepath = os.path.join(output_dir, f"bing_{len(downloaded)}.jpg")
                    with open(filepath, "wb") as f:
                        f.write(img_resp.content)
                    downloaded.append(filepath)
            except Exception:
                continue
    except Exception as e:
        log.warning("Bing fallback also failed: %s", e)
    
    return downloaded

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
        amazon_url = row.get("amazon_url", "")
        if not title:
            continue
            
        rank = row.get("rank", 0)
        asset_dir = f"assets/{rank}"
        
        log.info("Fetching images for: %s", title[:50])
        
        # Try Amazon first, fall back to Bing
        image_paths = fetch_amazon_images(amazon_url, num_images=3, output_dir=asset_dir)
        
        if not image_paths:
            # Bing fallback with product title
            search_query = title.split("-")[0].split("|")[0].strip()
            image_paths = _bing_fallback(asset_dir, 3, search_query)
        
        if image_paths:
            log.info("  → Got %d images for rank #%s", len(image_paths), rank)
        else:
            log.warning("  → No images found for rank #%s", rank)
        
        product_data = {
            "rank": rank,
            "title": title,
            "hook_idea": row.get("hook_idea", ""),
            "gemini_reason": row.get("gemini_reason", ""),
            "price": row.get("price", ""),
            "amazon_url": amazon_url,
            "images": image_paths
        }
        payload.append(product_data)
        
    # Save payload locally to pass to Phase 2
    os.makedirs("data", exist_ok=True)
    with open("data/phase1_payload.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        
    log.info("Phase 1 complete. %d products with images saved to data/phase1_payload.json", len(payload))
    return payload

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    run_phase1()
