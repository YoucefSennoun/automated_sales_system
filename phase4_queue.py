"""
Phase 4 — Staging for n8n
Reads Phase 3 payload, uploads the final MP4 videos to Google Drive, 
and logs them into a 'Content_Queue' Google Sheet for n8n to process.
"""

import os
import json
import base64
import logging
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
import gspread

from config import GSHEET_CREDENTIALS_B64, GSHEET_SPREADSHEET_ID, DRIVE_FOLDER_ID
from sheets_output import SCOPES

log = logging.getLogger(__name__)

def _get_credentials():
    if not GSHEET_CREDENTIALS_B64:
        raise ValueError("GSHEET_CREDENTIALS_B64 env variable not set")
    creds_dict = json.loads(base64.b64decode(GSHEET_CREDENTIALS_B64).decode("utf-8"))
    return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

import requests

def upload_to_transfer_sh(file_path: str) -> str:
    """Uploads a file to transfer.sh (free, keeps for 14 days, direct link) to bypass Drive quotas."""
    if not os.path.exists(file_path):
        log.error("File not found: %s", file_path)
        return ""

    try:
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            resp = requests.put(f"https://transfer.sh/{filename}", data=f, timeout=120)
            resp.raise_for_status()
            
            # transfer.sh returns the URL in plain text (e.g., https://transfer.sh/1a2b3c/video.mp4)
            direct_link = resp.text.strip()
            log.info("Uploaded %s to transfer.sh. Link: %s", file_path, direct_link)
            return direct_link

    except Exception as e:
        log.error("Transfer.sh upload failed for %s: %s", file_path, e)
        return ""

def update_content_queue(product_title: str, video_link: str, caption_text: str):
    """Appends a row to the Content_Queue worksheet."""
    try:
        creds = _get_credentials()
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GSHEET_SPREADSHEET_ID)
        
        worksheet_name = "Content_Queue"
        try:
            ws = sheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            # Create if it doesn't exist
            ws = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=5)
            headers = ["Date", "Product Title", "Video Link", "Caption + Hashtags", "Status"]
            ws.update("A1", [headers])
            log.info("Created worksheet: %s", worksheet_name)
            
        today = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        row = [today, product_title, video_link, caption_text, "Pending"]
        
        ws.append_row(row, value_input_option="USER_ENTERED")
        log.info("Added %s to Content_Queue", product_title[:20])
        
    except Exception as e:
        log.error("Failed to update Content_Queue sheet: %s", e)

def run_phase4():
    log.info("Starting Phase 4: Staging for n8n")
    
    if not os.path.exists("data/phase3_payload.json"):
        log.error("data/phase3_payload.json not found! Run Phase 3 first.")
        return
        
    with open("data/phase3_payload.json", "r", encoding="utf-8") as f:
        products = json.load(f)
        
    for p in products:
        video_path = p.get("video_path")
        if not video_path:
            continue
            
        log.info("Staging video for: %s", p["title"][:50])
        video_link = upload_to_transfer_sh(video_path)
        
        if video_link:
            # Combine hook and hashtags for the social media caption
            script_data = p.get("video_script", {})
            hashtags = script_data.get("hashtags", "")
            hook = p.get("hook_idea", "")
            
            caption_text = f"{hook}\n\nLink in bio! 🛒\n{hashtags}"
            update_content_queue(p["title"], video_link, caption_text)
            
    log.info("Phase 4 complete.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    run_phase4()
