"""
Phase 0 — Configuration
All settings live here. Sensitive values come from environment variables.
"""

import os

# ── Amazon ─────────────────────────────────────────────────────────────────
# Category slugs from amazon.com/gp/bestsellers/<slug>
# Pick the ones that match what PlusBase carries in your store
AMAZON_CATEGORIES = [
    "home-garden",
    "beauty",
    "health-personal-care",
    "sports-and-outdoors",
    "toys-and-games",
    "pet-supplies",
    "kitchen",
]

# How many top products to pull per category
AMAZON_TOP_N = 20

# Delay between requests (seconds) — keeps Amazon happy, avoids blocks
AMAZON_REQUEST_DELAY = 3

# Rotate user agents to avoid basic bot detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
]

# ── Google Trends ───────────────────────────────────────────────────────────
TRENDS_TIMEFRAME = "now 7-d"   # last 7 days — catches fast-rising products
TRENDS_GEO       = ""          # "" = worldwide; "US" = US only

# ── TikTok signal ───────────────────────────────────────────────────────────
# We estimate TikTok presence via Google search result count for:
# site:tiktok.com "<product keyword>"
# Not perfect but free and no auth needed.
TIKTOK_SEARCH_DELAY = 2        # seconds between Google searches

# ── Scoring weights (must sum to 1.0) ──────────────────────────────────────
SCORE_WEIGHT_AMAZON = 0.45
SCORE_WEIGHT_TRENDS = 0.35
SCORE_WEIGHT_TIKTOK = 0.20

# ── Filtering ───────────────────────────────────────────────────────────────
# Products with a combined score below this are dropped before Gemini sees them
MIN_SCORE_THRESHOLD = 0.30

# Final shortlist size sent to the pipeline
SHORTLIST_SIZE = 5

# ── Gemini ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL     = "gemini-2.5-flash"
GEMINI_API_URL   = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# ── Google Sheets output ────────────────────────────────────────────────────
# Service account JSON stored as an env variable (base64-encoded)
GSHEET_CREDENTIALS_B64 = os.getenv("GSHEET_CREDENTIALS_B64", "")
GSHEET_SPREADSHEET_ID  = os.getenv("GSHEET_SPREADSHEET_ID", "")
GSHEET_WORKSHEET_NAME  = "Phase0_Products"

# ── PlusBase ────────────────────────────────────────────────────────────────
# Your store URL — used to cross-check if a product is available
PLUSBASE_STORE_URL = os.getenv("PLUSBASE_STORE_URL", "")
