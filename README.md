# Phase 0 — Product Research Pipeline

Automatically finds trending, sellable products every day.
Zero cost. Runs on GitHub Actions free tier.

## What it does

1. Scrapes Amazon Best Sellers across 7 categories
2. Checks Google Trends for search velocity (last 7 days)
3. Estimates TikTok presence via Google search
4. Scores and ranks all products
5. Filters to products available in your PlusBase store
6. Gemini AI removes bad picks and adds video hook ideas
7. Writes the daily top 5 to your Google Sheet → feeds Phase 1

---

## One-time setup (30 minutes)

### 1. Gemini API key (free)
1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key

### 2. Google Sheets credentials
1. Go to https://console.cloud.google.com
2. Create a new project (or use existing)
3. Enable: **Google Sheets API** and **Google Drive API**
4. Go to IAM → Service Accounts → Create Service Account
5. Download the JSON key file
6. Base64-encode it:
   ```bash
   base64 -w 0 credentials.json
   ```
7. Copy the output (this is your GSHEET_CREDENTIALS_B64)
8. Create a Google Sheet → share it with the service account email
9. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit`

### 3. GitHub repository secrets
Go to your repo → Settings → Secrets and variables → Actions → New secret

Add these 4 secrets:
| Secret name | Value |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key |
| `GSHEET_CREDENTIALS_B64` | Base64-encoded service account JSON |
| `GSHEET_SPREADSHEET_ID` | Your Google Sheet ID |
| `PLUSBASE_STORE_URL` | e.g. `https://yourstore.myshopify.com` |

### 4. Push to GitHub
```bash
git init
git add .
git commit -m "Phase 0-4 — complete automated pipeline"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

The workflow runs automatically at 06:00 UTC every day.
To test immediately: GitHub → Actions → Phase 0 → Run workflow.

---

# Phase 1-4 — Content Creation Pipeline

This new pipeline runs after Phase 0. It takes the top products, writes a viral TikTok script, generates an AI voiceover, stitches scraped images into a video, and queues it for n8n to post.

## Setup Requirements

1. **System Dependencies**: The video generator (`moviepy`) requires `ImageMagick` to be installed on your system (or GitHub Actions runner) to generate text captions.
2. **Google Drive Folder**: Create a Google Drive folder and share it with your service account email. Get the Folder ID from the URL (`folders/THIS_IS_THE_ID`).
3. **Add Secret**: Add `DRIVE_FOLDER_ID` to your GitHub repository secrets.

To run locally:
```bash
pip install -r requirements.txt
python main_content.py
```

---

## Output

The Google Sheet gets a new row for each product daily:

| Column | Description |
|---|---|
| date | When this was generated |
| rank | 1 = best pick of the day |
| title | Product name |
| combined_score | 0–1, higher is better |
| hook_idea | Gemini-generated TikTok hook |
| status | `pending` → Phase 1 updates to `scripted` |

---

## Adjust categories

Edit `config.py` → `AMAZON_CATEGORIES` to match what your store sells.
Full list of Amazon category slugs: https://www.amazon.com/gp/bestsellers/

## Adjust scoring weights

Edit `config.py`:
```python
SCORE_WEIGHT_AMAZON = 0.45  # Amazon rank importance
SCORE_WEIGHT_TRENDS = 0.35  # Google Trends importance
SCORE_WEIGHT_TIKTOK = 0.20  # TikTok presence importance
```

---

## Troubleshooting

**Amazon returns no products**
Amazon has bot detection. If it blocks you, add more delay:
`AMAZON_REQUEST_DELAY = 6` in config.py

**Google Trends rate limit error**
Reduce batch sizes or increase `DELAY_BETWEEN_BATCHES` in trends_scraper.py

**Gemini returns invalid JSON**
The filter falls back to returning the top 5 scored products unfiltered.
Check the log artifact for the raw Gemini response.

**Sheet write fails**
Verify the service account email has Editor access to the Sheet.
