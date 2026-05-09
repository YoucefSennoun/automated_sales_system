"""
Phase 0 — Configuration
All settings live here. Sensitive values come from environment variables.
"""

import os

# ── Amazon ──────────────────────────────────────────────────────────────────
AMAZON_CATEGORIES = [
    "home-garden",
    "beauty",
    "health-personal-care",
    "sports-and-outdoors",
    "toys-and-games",
    "pet-supplies",
    "kitchen",
]

AMAZON_TOP_N          = 20
AMAZON_REQUEST_DELAY  = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
]

# ── Signal toggles ──────────────────────────────────────────────────────────
# Both kept True — GitHub/cloud IPs are rate-limited by Google for both.
# Scorer automatically redistributes weights when these are skipped.
SKIP_TRENDS  = True
SKIP_TIKTOK  = True
SKIP_PLUSBASE = True   # set False once your PLUSBASE_STORE_URL is configured

# ── Google Trends (used only when SKIP_TRENDS = False) ──────────────────────
TRENDS_TIMEFRAME      = "now 7-d"
TRENDS_GEO            = ""
MAX_RETRIES           = 3
BACKOFF               = 15
TIKTOK_SEARCH_DELAY   = 15

# ── Scoring weights ─────────────────────────────────────────────────────────
# These are the BASE weights. Scorer normalizes them dynamically
# based on which signals are active (SKIP_* flags above).
SCORE_WEIGHT_AMAZON = 0.45
SCORE_WEIGHT_TRENDS = 0.35
SCORE_WEIGHT_TIKTOK = 0.20

# ── Filtering ───────────────────────────────────────────────────────────────
# With SKIP_TRENDS=True and SKIP_TIKTOK=True, scorer uses Amazon weight only
# (normalized to 1.0), so scores go 0–1 as normal. Threshold of 0.25 keeps
# roughly top 15 products out of 20 per category for Gemini to review.
MIN_SCORE_THRESHOLD = 0.25

SHORTLIST_SIZE = 5

# ── Gemini ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-2.5-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# ── Google Sheets ────────────────────────────────────────────────────────────
GSHEET_CREDENTIALS_B64 = os.getenv("GSHEET_CREDENTIALS_B64", "")
GSHEET_SPREADSHEET_ID  = os.getenv("GSHEET_SPREADSHEET_ID", "")
GSHEET_WORKSHEET_NAME  = "Phase0_Products"

# ── PlusBase ─────────────────────────────────────────────────────────────────
PLUSBASE_STORE_URL = os.getenv("PLUSBASE_STORE_URL", "")

# ── Google Drive (Phase 4) ───────────────────────────────────────────────────
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "")