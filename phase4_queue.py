"""
Phase 4 — Staging for n8n
Reads Phase 3 payload and logs the generated videos into a 'Content_Queue' 
Google Sheet for n8n to process.

Videos are stored as GitHub Actions artifacts (downloadable from the Actions page).
"""

import os
import json
import base64
import logging
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread

from config import GSHEET_CREDENTIALS_B64, GSHEET_SPREADSHEET_ID
from sheets_output import SCOPES

log = logging.getLogger(__name__)

def _get_credentials():
    if not GSHEET_CREDENTIALS_B64:
        raise ValueError("GSHEET_CREDENTIALS_B64 env variable not set")
    creds_dict = json.loads(base64.b64decode(GSHEET_CREDENTIALS_B64).decode("utf-8"))
    return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

def update_content_queue(product_title: str, video_filename: str, caption_text: str):
    """Appends a row to the Content_Queue worksheet."""
    try:
        creds = _get_credentials()
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GSHEET_SPREADSHEET_ID)
        
        worksheet_name = "Content_Queue"
        try:
            ws = sheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=6)
            headers = ["Date", "Product Title", "Video File", "Caption + Hashtags", "Status", "Notes"]
            ws.update("A1", [headers])
            log.info("Created worksheet: %s", worksheet_name)
            
        today = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        run_id = os.getenv("GITHUB_RUN_ID", "local")
        repo = os.getenv("GITHUB_REPOSITORY", "")
        
        if repo and run_id != "local":
            notes = f"Download from: github.com/{repo}/actions/runs/{run_id}"
        else:
            notes = f"Local file: {video_filename}"
            
        row = [today, product_title, video_filename, caption_text, "Pending", notes]
        
        ws.append_row(row, value_input_option="USER_ENTERED")
        log.info("Added %s to Content_Queue", product_title[:30])
        
    except Exception as e:
        log.error("Failed to update Content_Queue sheet: %s", e)

def run_phase4():
    log.info("Starting Phase 4: Staging for n8n")
    
    if not os.path.exists("data/phase3_payload.json"):
        log.error("data/phase3_payload.json not found! Run Phase 3 first.")
        return
        
    with open("data/phase3_payload.json", "r", encoding="utf-8") as f:
        products = json.load(f)
    
    queued = 0
    for p in products:
        video_path = p.get("video_path")
        if not video_path:
            continue
            
        log.info("Queuing video for: %s", p["title"][:50])
        
        script_data = p.get("video_script", {})
        hashtags = script_data.get("hashtags", "")
        hook = p.get("hook_idea", "")
        
        caption_text = f"{hook}\n\nLink in bio! 🛒\n{hashtags}"
        video_filename = os.path.basename(video_path)
        
        update_content_queue(p["title"], video_filename, caption_text)
        queued += 1
            
    log.info("Phase 4 complete. Queued %d videos to Content_Queue sheet.", queued)
    log.info("Videos are saved as GitHub Actions artifacts — download from the Actions page.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    run_phase4()
