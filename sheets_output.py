"""
Phase 0 — Google Sheets output
Writes the daily product shortlist to a Google Sheet.

Fix: checks if today's date already has entries before writing,
preventing duplicate rows from multiple workflow runs on the same day.
"""

import base64
import csv
import json
import logging
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from config import GSHEET_CREDENTIALS_B64, GSHEET_SPREADSHEET_ID, GSHEET_WORKSHEET_NAME

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "date", "rank", "title", "category", "price",
    "combined_score", "amazon_score", "trends_score", "tiktok_score",
    "store_match", "hook_idea", "gemini_reason", "amazon_url", "status",
]


def _get_client() -> gspread.Client:
    if not GSHEET_CREDENTIALS_B64:
        raise ValueError("GSHEET_CREDENTIALS_B64 env variable not set")
    creds_dict  = json.loads(base64.b64decode(GSHEET_CREDENTIALS_B64).decode("utf-8"))
    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(credentials)


def _ensure_headers(ws: gspread.Worksheet) -> None:
    if ws.row_values(1) != HEADERS:
        ws.update("A1", [HEADERS])
        log.info("Headers written to sheet")


def _today_already_written(ws: gspread.Worksheet, today: str) -> bool:
    """
    Returns True if today's date already appears in column A (date column).
    Prevents duplicate writes when workflow is triggered multiple times.
    """
    try:
        date_col = ws.col_values(1)   # column A = date
        return today in date_col
    except Exception:
        return False


def _build_row(today: str, rank: int, p: dict) -> list:
    return [
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
        "pending",
    ]


def write_shortlist(products: list[dict]) -> bool:
    if not products:
        log.warning("No products to write")
        return False

    today = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        client = _get_client()
        sheet  = client.open_by_key(GSHEET_SPREADSHEET_ID)
        try:
            ws = sheet.worksheet(GSHEET_WORKSHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            ws = sheet.add_worksheet(title=GSHEET_WORKSHEET_NAME, rows=1000, cols=len(HEADERS))
            log.info("Created worksheet: %s", GSHEET_WORKSHEET_NAME)

        _ensure_headers(ws)

        # ── Duplicate guard ──────────────────────────────────────────────────
        if _today_already_written(ws, today):
            log.warning(
                "Sheet already has entries for %s — skipping write to avoid duplicates. "
                "If you want to overwrite, manually delete today's rows first.", today
            )
            return True  # not a failure — data is already there

        rows = [_build_row(today, rank, p) for rank, p in enumerate(products, 1)]
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        log.info("Written %d products to Google Sheet (%s)", len(rows), today)
        return True

    except Exception as e:
        log.error("Failed to write to Google Sheet: %s", e)

        # Fallback: write to local CSV (uploaded as GitHub Actions artifact)
        fallback = os.path.join(os.getcwd(), f"shortlist_fallback_{today}.csv")
        try:
            with open(fallback, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(HEADERS)
                for rank, p in enumerate(products, 1):
                    writer.writerow(_build_row(today, rank, p))
            log.warning("Wrote fallback CSV: %s", fallback)
            return True
        except Exception as fe:
            log.error("Fallback CSV also failed: %s", fe)
            return False