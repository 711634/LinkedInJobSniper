# 🕵️‍♂️ LinkedIn Job Sniper

An automated AI agent that scrapes LinkedIn daily, scores jobs against your resume, tailors your CV bullets for top matches, and emails you the results every morning — completely free.

## ✨ Features

- 🔍 **Multi-Term Scraping**: Searches 13 job titles simultaneously across London
- 🧠 **AI Scoring**: Uses Groq (free) + LangChain to score every job 0–100 against your resume
- ✨ **CV Tailoring**: For jobs scoring ≥75, automatically rewrites your resume bullets to match the job's keywords
- 📊 **Google Sheets Tracker**: Exports all top matches to a Google Sheet so you can track what you've applied to
- 📧 **Daily Email Digest**: HTML email with scores, tailored bullets, YoE, and Apply buttons
- ☁️ **Zero Cost**: Runs entirely on GitHub Actions (free) + Groq API (free tier)
- 🚫 **No Proxy Needed**: Works without any paid proxy service

## 🚀 How It Works

1. **Trigger**: Runs automatically every day at 8:00 AM UTC via GitHub Actions cron
2. **Scrape**: Fetches fresh LinkedIn jobs across 13 search terms in London
3. **Deduplicate**: Removes duplicate listings across search terms
4. **Evaluate**: Groq AI reads your resume and scores every job (0–100)
5. **Tailor**: For jobs scoring ≥75, rewrites your CV bullets to mirror the job's language
6. **Export**: Appends all top matches to your Google Sheet tracker
7. **Email**: Sends you the top 15 jobs with tailored bullets and Apply buttons

## ⚙️ Setup

### 1. Fork this repo

Click **Fork** → **Create fork**

### 2. Get a Groq API Key (Free)

- Go to [https://console.groq.com](https://console.groq.com)
- Sign up and create an API key
- No credit card required — generous free tier

### 3. Set up Gmail App Password

- Go to [https://myaccount.google.com/security](https://myaccount.google.com/security)
- Enable 2-Step Verification
- Search "App passwords" → Generate one for "Mail"
- Copy the 16-character password

### 4. Set up Google Cloud (for Sheets + optional Drive resume)

- Go to [https://console.cloud.google.com](https://console.cloud.google.com)
- Create a new project
- Go to **APIs & Services → Enable APIs** and enable:
  - ✅ Google Sheets API
  - ✅ Google Drive API (only if using Drive for your resume)
- Go to **IAM & Admin → Service Accounts → Create Service Account**
- Give it any name, click **Create**
- Click the service account → **Keys → Add Key → JSON** → download it
- Create a Google Sheet and share it with the service account's email (Editor access)
- Copy the Sheet ID from the URL: `docs.google.com/spreadsheets/d/`**THIS_PART**`/edit`

### 5. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value | Required? |
|--------|-------|-----------|
| `API_KEY` | Your Groq API key (`gsk_...`) | ✅ |
| `API_BASE` | `https://api.groq.com/openai/v1` | ✅ |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | ✅ |
| `EMAIL_SENDER` | Your Gmail address | ✅ |
| `EMAIL_PASSWORD` | Gmail App Password | ✅ |
| `EMAIL_RECEIVER` | Email to receive reports | ✅ |
| `RESUME_TEXT` | Your full resume as plain text | ✅ |
| `SCORE_THRESHOLD` | Minimum score to include (e.g. `50`) | ✅ |
| `GOOGLE_SHEET_ID` | ID from your Google Sheet URL | ✅ |
| `GCP_CREDENTIALS_JSON` | Paste entire contents of your service account JSON | ✅ |
| `CRITERIA` | Optional extra scoring instructions | Optional |
| `RESUME_FILE_ID` | File ID from Google Drive resume URL | Optional |

### 6. Enable Actions & Run

- Go to the **Actions** tab → enable workflows
- Click **Daily Career Scout** → **Run workflow** to test manually
- Check your inbox and Google Sheet after ~5 minutes ✅

## 🔧 Customisation

Edit `main.py` to change search terms, location, or thresholds:

```python
SEARCH_TERMS = [
    "Junior Product Manager",
    "Graduate Finance Analyst",
    "Junior Business Analyst",
    "Graduate Operations Analyst",
    "Junior Data Analyst",
    "Graduate Scheme Finance",
    "Associate Product Manager",
    "Strategy and Operations Analyst",
    "GTM Associate",
    "Operations Associate",
    "Graduate Customer Success Manager",
    "Business Development Associate",
    "Graduate Consultant",
]
LOCATIONS        = ["London, England"]
RESULT_LIMIT     = 15    # per search term
HOURS_OLD        = 24
SCORE_THRESHOLD  = 50    # minimum score to appear in email
TAILOR_THRESHOLD = 75    # minimum score to generate tailored CV bullets
```

## 📊 Google Sheets Tracker

Every daily run appends matched jobs to your sheet with these columns:

| Date | Score | Title | Company | YoE | Reason | URL | Applied? |
|------|-------|-------|---------|-----|--------|-----|----------|

Manually update the **Applied?** column as you go to track your pipeline.

## ⏰ Schedule

Runs daily at **8:00 AM UTC** (8:00 AM GMT / 9:00 AM BST in summer).

To change, edit `.github/workflows/linkedin-job-sniper.yml`:

```yaml
- cron: '0 8 * * *'  # 8am UTC daily
```

## ⚠️ Disclaimer

For educational purposes only. Web scraping may violate LinkedIn's Terms of Service. Use responsibly and at your own risk.

## 👨‍💻 Author

Misbah — built on top of the original [LinkedInJobSniper](https://github.com/tao-991/LinkedInJobSniper) by Tao.  
Powered by Python, LangChain, Groq & GitHub Actions ☕
