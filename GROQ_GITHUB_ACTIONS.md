# Run Job Sniper Every Morning with Groq (Free) + GitHub Actions

Once **local runs work** with Ollama, you can run the job sniper **every morning in the cloud** so your Mac doesn’t need to be on. Use a **free Groq API key** and GitHub Actions.

---

## 0. Create your own GitHub repo (if you don’t have one)

Right now your folder is tied to the **original** repo (`tao-991/LinkedInJobSniper`). You need **your own** repo so you can add secrets and run Actions.

1. **Create a new repo on GitHub**
   - Go to [github.com/new](https://github.com/new)
   - Name it e.g. `LinkedInJobSniper` (or any name)
   - Choose **Private** if you don’t want your code public
   - Do **not** add a README, .gitignore, or license (you already have them)
   - Click **Create repository**

2. **Point this project at your new repo and push**
   - In terminal, from your project folder run (replace `YOUR_USERNAME` with your GitHub username):
   ```bash
   git remote rename origin upstream
   git remote add origin https://github.com/YOUR_USERNAME/LinkedInJobSniper.git
   git add -A
   git commit -m "Add Groq + 8am schedule for GitHub Actions"
   git push -u origin main
   ```
   - If the new repo already has a different default branch (e.g. `master`), use that instead of `main`, or rename on GitHub to `main`.

3. **Add the secrets** in **your** repo (Step 2 below).

---

## 1. Get a free Groq API key

1. Go to [https://console.groq.com](https://console.groq.com) and sign up / log in.
2. Open **API Keys** and create a key (e.g. name: `JobSniper`).
3. Copy the key (starts with `gsk_...`) and **store it only in GitHub Secrets**. Never paste it in chat, code, or commit it.

> ⚠️ **If you ever paste a key by mistake:** go to console.groq.com → API Keys → delete that key and create a new one. Use only the new key in GitHub Secrets.

## 2. Add GitHub Secrets for Groq

In your repo: **Settings → Secrets and variables → Actions**. Add (or update) these secrets:

| Secret        | Value |
|---------------|--------|
| `API_KEY`     | Your Groq API key (e.g. `gsk_...`) |
| `API_BASE`    | `https://api.groq.com/openai/v1` |
| `LLM_MODEL`   | `llama-3.1-8b-instant` |

Keep your existing secrets for email and resume:

- `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECEIVER`
- `PROXY_URL` (required for LinkedIn scraping in CI)
- `RESUME_TEXT` (or `GCP_CREDENTIALS_JSON` + `RESUME_FILE_ID`)
- `CRITERIA` (optional)

## 3. GitHub environment (optional)

The workflow uses `environment: JobSniperEnvVar`. Either:

- Create an environment named `JobSniperEnvVar` under **Settings → Environments** and add the same secrets there, or  
- Remove the `environment: JobSniperEnvVar` line from `.github/workflows/daily.yml` so the job uses the repo’s Actions secrets only.

## 4. Schedule

The workflow is set to run at **08:00 UTC** daily (~8am London in winter). You can trigger it manually anytime: **Actions → Daily Career Scout → Run workflow**. To change the time, edit the `cron` in `.github/workflows/daily.yml` (e.g. `0 7 * * *` for 7am UTC).

## Summary

- **Local:** `.env` uses `API_KEY=ollama`, `API_BASE=http://localhost:11434/v1`, and no `LLM_MODEL` (defaults to `mistral`).
- **GitHub Actions:** Use Groq by setting `API_KEY`, `API_BASE`, and `LLM_MODEL` as above. No Mac needed; runs in the cloud every morning.
