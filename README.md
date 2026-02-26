# 🕵️‍♂️ LinkedIn Job Sniper

An automated AI agent that scrapes LinkedIn daily, scores jobs against your resume, and emails you the top matches every morning — completely free.

## ✨ Features

- 🔍 **Multi-Term Scraping**: Searches multiple job titles simultaneously across London
- 🧠 **AI Scoring**: Uses Groq (free) + LangChain to score every job 0–100 against your resume
- 📧 **Daily Email Digest**: HTML email with scores, company, YoE required, and Apply buttons
- ☁️ **Zero Cost**: Runs entirely on GitHub Actions (free) + Groq API (free tier)
- 🚫 **No Proxy Needed**: Works without any paid proxy service

## 🚀 How It Works

1. **Trigger**: Runs automatically every day at 8:00 AM UTC via GitHub Actions cron
2. **Scrape**: Fetches fresh LinkedIn jobs across 6+ search terms in London
3. **Deduplicate**: Removes duplicate listings across search terms
4. **Evaluate**: Groq AI reads your resume and scores every job (0–100)
5. **Email**: Filters jobs above your score threshold and emails the top 15

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

### 4. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|--------|-------|
| `API_KEY` | Your Groq API key (`gsk_...`) |
| `API_BASE` | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` |
| `EMAIL_SENDER` | Your Gmail address |
| `EMAIL_PASSWORD` | Gmail App Password |
| `EMAIL_RECEIVER` | Email to receive reports |
| `RESUME_TEXT` | Your full resume as plain text |
| `SCORE_THRESHOLD` | Minimum score to include (e.g. `50`) |
| `CRITERIA` | Optional extra scoring instructions |

### 5. Enable Actions & Run

- Go to the **Actions** tab → enable workflows
- Click **Daily Career Scout** → **Run workflow** to test manually
- Check your inbox after ~5 minutes ✅

## 🔧 Customisation

Edit `main.py` to change search terms or location:

```python
SEARCH_TERMS = [
    "Junior Product Manager",
    "Graduate Finance Analyst",
    "Junior Business Analyst",
    "Graduate Operations Analyst",
    "Junior Data Analyst",
    "Graduate Scheme Finance",
]
LOCATIONS    = ["London, England"]
RESULT_LIMIT = 15   # per search term
HOURS_OLD    = 24
```

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
