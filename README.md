# Automated Sales System

Finds trending dropshippable products daily, generates TikTok scripts automatically,
and gives you a 10-minute filming briefing every morning.

## How it works

**Automated (runs at 6am UTC daily via GitHub Actions):**
1. Scrapes Amazon Best Sellers across 7 categories
2. Scores products by rank
3. Gemini AI filters out branded/non-dropshippable items and writes TikTok hooks
4. Writes top 3 products to your `Phase0_Products` Google Sheet
5. Generates a full TikTok script and shot list for each product
6. Writes the filming briefing to your `Content_Queue` Google Sheet

**Manual (10 minutes per day):**
7. Open `Content_Queue` — read today's product, script, and shot list
8. Make the video in CapCut (script-to-video) or Meta AI (text-to-video)
9. Drop the video in your Google Drive posting folder
10. n8n posts it to TikTok/Instagram automatically on your schedule

## Setup

### GitHub Secrets required

| Secret | Where to get it |
|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/app/apikey |
| `GSHEET_CREDENTIALS_B64` | Google Cloud → Service Account → JSON key → base64 encoded |
| `GSHEET_SPREADSHEET_ID` | From your Google Sheet URL |
| `PLUSBASE_STORE_URL` | Your store URL (optional, leave blank to skip) |

### Google Sheet setup
1. Create a new Google Sheet
2. Create a Service Account in Google Cloud Console
3. Enable Google Sheets API and Google Drive API
4. Share the sheet with the service account email (Editor access)
5. Base64-encode the service account JSON: `base64 -w 0 credentials.json`
6. Add the result as the `GSHEET_CREDENTIALS_B64` secret

### Run manually
```bash
pip install -r requirements.txt
python main.py          # Phase 0: product research
python main_content.py  # Phase 2+4: script generation
```

## Output sheets

**Phase0_Products** — daily product shortlist
| Column | Description |
|---|---|
| date | Run date |
| rank | 1 = best pick |
| title | Product name |
| combined_score | 0–1 score |
| hook_idea | Gemini-generated TikTok hook |
| status | pending / scripted |

**Content_Queue** — daily filming briefing
| Column | Description |
|---|---|
| product_title | What to find/source |
| hook | Opening line for the video |
| voiceover | Full script (40-55 words) |
| captions | On-screen text |
| hashtags | Post hashtags |
| visual_direction | Shot-by-shot filming guide |
| status | ready_to_film / posted |

## Making videos (10 minutes)

**CapCut (recommended):**
Open CapCut → Script to Video → paste the voiceover from Content_Queue → pick a style → generate → download

**Meta AI:**
Go to meta.ai → describe the product scene → generate → download

**Film yourself:**
Follow the visual_direction column — 3-4 shots with your phone is enough

## Adjust product categories

Edit `config.py` → `AMAZON_CATEGORIES`. Current list targets dropshippable items.
Full slug list: https://www.amazon.com/gp/bestsellers/
