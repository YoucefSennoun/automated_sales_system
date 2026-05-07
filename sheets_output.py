"""
Phase 0 — Google Sheets output
Writes the daily product shortlist to a Google Sheet.
This sheet acts as the handoff point to Phase 1 (script generation).

Setup (one-time):
1. Go to console.cloud.google.com → enable Google Sheets API
2. Create a Service Account → download JSON key
3. Share your Google Sheet with the service account email
4. Base64-encode the JSON key: base64 credentials.json
5. Add as GitHub secret: GSHEET_CREDENTIALS_B64
"""

import base64
import json
import logging
import tempfile
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from config import GSHEET_CREDENTIALS_B64, GSHEET_SPREADSHEET_ID, GSHEET_WORKSHEET_NAME

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Column headers written to row 1 of the sheet
HEADERS = [
    "date",
    "rank",
    "title",
    "category",
    "price",
    "combined_score",
    "amazon_score",
    "trends_score",
    "tiktok_score",
    "store_match",
    "hook_idea",
    "gemini_reason",
    "amazon_url",
    "status",          # pipeline uses this: "pending" / "scripted" / "posted"
]


def _get_client() -> gspread.Client:
    """Authenticate using the base64-encoded service account credentials."""
    if not GSHEET_CREDENTIALS_B64:
        raise ValueError("GSHEET_CREDENTIALS_B64 env variable not set")

    creds_json = base64.b64decode(GSHEET_CREDENTIALS_B64).decode("utf-8")
    creds_dict = json.loads(creds_json)

    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(credentials)


def _ensure_headers(worksheet: gspread.Worksheet) -> None:
    """Write headers if the sheet is empty."""
    existing = worksheet.row_values(1)
    if existing != HEADERS:
        worksheet.update("A1", [HEADERS])
        log.info("Headers written to sheet")


def write_shortlist(products: list[dict]) -> bool:
    """
    Appends today's shortlist to the Google Sheet.
    Returns True on success, False on failure.
    """
    if not products:
        log.warning("No products to write")
        return False

    try:
        client    = _get_client()
        sheet     = client.open_by_key(GSHEET_SPREADSHEET_ID)
        worksheet = sheet.worksheet(GSHEET_WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        # Create the worksheet if it doesn't exist yet
        sheet     = client.open_by_key(GSHEET_SPREADSHEET_ID)
        worksheet = sheet.add_worksheet(
            title=GSHEET_WORKSHEET_NAME, rows=1000, cols=len(HEADERS)
        )
        log.info("Created worksheet: %s", GSHEET_WORKSHEET_NAME)

    _ensure_headers(worksheet)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    rows  = []

    for rank, p in enumerate(products, 1):
        row = [
            today,
            rank,
            p.get("title", ""),
            p.get("category", ""),
            p.get("price", ""),
            p.get("combined_score", 0),
            p.get("amazon_score", 0),
            p.get("trends_score", 0),
            p.get("tiktok_score", 0),
            p.get("store_match", ""),
            p.get("hook_idea", ""),
            p.get("gemini_reason", ""),
            p.get("url", ""),
            "pending",    # Phase 1 will update this to "scripted"
        ]
        rows.append(row)

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    log.info("Written %d products to Google Sheet (%s)", len(rows), today)
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mock = [
        {
            "title": "Portable Neck Massager", "category": "health",
            "price": "$29.99", "combined_score": 0.82,
            "amazon_score": 0.90, "trends_score": 0.75, "tiktok_score": 0.80,
            "store_match": "Electric Neck Shoulder Massager",
            "hook_idea": "POV: your neck hasn't felt this good in years",
            "gemini_reason": "Clear demo potential, solves visible pain",
            "url": "https://amazon.com/dp/B09EXAMPLE",
        }
    ]
    success = write_shortlist(mock)
    print("Write successful:", success)
