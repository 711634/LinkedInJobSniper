import os, smtplib, json, io, time, random
from typing import List
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import pandas as pd
from dotenv import load_dotenv
from jobspy import scrape_jobs

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from pypdf import PdfReader

load_dotenv()

# ── Config ────────────────────────────────────────────────
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
RESULT_LIMIT     = 8
HOURS_OLD        = 24
SCORE_THRESHOLD  = int(os.getenv("SCORE_THRESHOLD", "45"))
TAILOR_THRESHOLD = 75
PROXY_URL        = os.getenv("PROXY_URL") or None
RESUME           = os.getenv("RESUME_TEXT") or None
API_KEY          = os.getenv("API_KEY")
BASE_URL         = os.getenv("API_BASE")
LLM_MODEL        = os.getenv("LLM_MODEL", "mistral")
CRITERIA         = os.getenv("CRITERIA", "")
SHEET_ID         = os.getenv("GOOGLE_SHEET_ID") or None

# ── Resume: Google Drive fallback ─────────────────────────
def load_resume_from_google_drive() -> str:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    creds_json_str = os.getenv("GCP_CREDENTIALS_JSON")
    file_id        = os.getenv("RESUME_FILE_ID")
    if not creds_json_str or not file_id:
        return None
    print("Loading resume from Google Drive...")
    try:
        creds_dict = json.loads(creds_json_str)
        creds      = service_account.Credentials.from_service_account_info(
                        creds_dict, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        service    = build('drive', 'v3', credentials=creds)
        req        = service.files().get_media(fileId=file_id)
        file_io    = io.BytesIO()
        downloader = MediaIoBaseDownload(file_io, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        file_io.seek(0)
        return "".join(p.extract_text() + "\n" for p in PdfReader(file_io).pages)
    except Exception as e:
        print(f"Google Drive load failed: {e}")
        return None

if not RESUME:
    RESUME = load_resume_from_google_drive()

# ── Guards ────────────────────────────────────────────────
if not RESUME:
    raise SystemExit("ERROR: No resume. Set RESUME_TEXT in .env or configure Google Drive.")
if not API_KEY:
    raise SystemExit("ERROR: No API_KEY set in .env")

# ── LLM setup ─────────────────────────────────────────────
llm = ChatOpenAI(model=LLM_MODEL, api_key=API_KEY, base_url=BASE_URL, temperature=0)

class JobEvaluation(BaseModel):
    score:  int = Field(description="Relevance score 0-100 based on resume match.")
    reason: str = Field(description="One-sentence reason for the score.")
    yoe:    str = Field(description="Years of experience required, or 'Not Specified'.")

structured_llm = llm.with_structured_output(JobEvaluation, method="json_mode")

system_template = """You are an expert career coach. Evaluate how well a job description matches a candidate's resume.
Return a score (0-100), years of experience required, and a one-sentence reason.
If YoE is not mentioned, return "Not Specified".

Scoring criteria:
1. Skill Match (50%): Alignment of required skills with resume.
2. Seniority Fit (30%): Is this an entry-level/graduate role suitable for the candidate?
3. Domain Fit (20%): Does the industry/function match the candidate's background?

Respond in JSON format with keys: score, reason, yoe.
""" + CRITERIA

eval_prompt = ChatPromptTemplate.from_messages([
    ("system", system_template),
    ("user", "RESUME:\n{resume}\n\nJOB TITLE: {title}\nJOB DESCRIPTION:\n{description}\n\nBe strict. Penalise roles requiring 3+ years experience.")
])
evaluation_chain = eval_prompt | structured_llm

# — Tailoring model —
tailor_llm = ChatOpenAI(model=LLM_MODEL, api_key=API_KEY, base_url=BASE_URL, temperature=0.4)

tailor_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert CV writer. Given a resume and a job description, rewrite 3-4 of the
most relevant bullet points from the candidate's experience to better mirror the job's language and keywords.
Keep the same facts — do NOT invent achievements or numbers. Output ONLY the rewritten bullet points as a
short HTML unordered list (<ul><li>...</li></ul>). No preamble, no explanation."""),
    ("user", "RESUME:\n{resume}\n\nJOB TITLE: {title}\nJOB DESCRIPTION:\n{description}")
])
tailor_chain = tailor_prompt | tailor_llm

def tailor_resume_for_job(title: str, description: str) -> str:
    try:
        result = tailor_chain.invoke({
            "resume":      RESUME[:2000],
            "title":       title,
            "description": description[:1500]
        })
        return result.content.strip()
    except Exception as e:
        print(f"  Tailoring failed for '{title}': {e}")
        return ""

# ── Google Sheets ─────────────────────────────────────────
def get_sheets_service():
    creds_json_str = os.getenv("GCP_CREDENTIALS_JSON")
    if not creds_json_str:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds_dict = json.loads(creds_json_str)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        return build('sheets', 'v4', credentials=creds)
    except Exception as e:
        print(f"Sheets service init failed: {e}")
        return None

def export_to_sheets(jobs: List[dict]):
    if not SHEET_ID:
        print("No GOOGLE_SHEET_ID set — skipping Sheets export.")
        return
    service = get_sheets_service()
    if not service:
        return
    try:
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SHEET_ID, range="Sheet1!A1:A1"
        ).execute()
        if not result.get("values"):
            header = [["Date", "Score", "Title", "Company", "YoE", "Reason", "URL", "Applied?"]]
            sheet.values().append(
                spreadsheetId=SHEET_ID,
                range="Sheet1!A1",
                valueInputOption="RAW",
                body={"values": header}
            ).execute()

        rows = [[
            datetime.now().strftime("%d %b %Y"),
            job["score"],
            job["title"],
            job["company"],
            job["yoe"],
            job["reason"],
            job["job_url"],
            "No"
        ] for job in jobs]

        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": rows}
        ).execute()
        print(f"Exported {len(rows)} jobs to Google Sheets ✅")
    except Exception as e:
        print(f"Sheets export failed: {e}")

# ── Scraping ──────────────────────────────────────────────
def get_jobs_data(location: str, search_term: str) -> pd.DataFrame:
    proxies = [PROXY_URL] if PROXY_URL else None
    print(f"\nSearching: '{search_term}' in '{location}'")
    for attempt in range(1, 4):
        try:
            jobs = scrape_jobs(
                site_name=["linkedin"],
                search_term=search_term,
                location=location,
                results_wanted=RESULT_LIMIT,
                hours_old=HOURS_OLD,
                proxies=proxies
            )
            print(f"  → {len(jobs)} jobs scraped")
            return jobs
        except Exception as e:
            print(f"  Attempt {attempt} failed: {e}")
            if attempt < 3:
                time.sleep(random.uniform(3, 6))
    return pd.DataFrame()

def fetch_missing_description(url: str) -> str:
    try:
        time.sleep(random.uniform(2, 4))
        headers  = {"User-Agent": UserAgent().random, "Accept-Language": "en-US,en;q=0.9"}
        proxies  = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
        response = requests.get(url, headers=headers, proxies=proxies, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            div  = (soup.find("div", {"class": "show-more-less-html__markup"}) or
                    soup.find("div", {"class": "description__text"}))
            return div.get_text(separator="\n").strip() if div else soup.get_text()[:5000]
    except Exception as e:
        print(f"  Manual fetch failed: {e}")
    return ""

# ── Evaluation ────────────────────────────────────────────
def evaluate_job(title: str, description: str) -> dict:
    if not description or len(str(description)) < 50:
        return {"score": 0, "reason": "No description", "yoe": "N/A"}
    try:
        result = evaluation_chain.invoke({
            "resume":      RESUME[:2000],
            "title":       title,
            "description": description[:1500]
        })
        return {"score": result.score, "reason": result.reason, "yoe": result.yoe}
    except Exception as e:
        print(f"  AI error for '{title}': {e}")
        return {"score": 0, "reason": "AI Error", "yoe": "N/A"}

# ── Email ─────────────────────────────────────────────────
def send_email(top_jobs: List[dict]):
    if not top_jobs:
        print("No jobs met the score threshold. No email sent.")
        return
    sender   = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver = os.getenv("EMAIL_RECEIVER")
    subject  = f"Job Sniper: {len(top_jobs)} Matches for {datetime.now().strftime('%d %b %Y')}"

    rows = ""
    for job in top_jobs:
        score_color = "#27ae60" if job['score'] >= 75 else "#e67e22"

        tailor_html = ""
        if job.get("tailored_bullets"):
            tailor_html = f"""
            <tr>
                <td colspan="6" style="padding:8px 10px 14px 10px;background:#f0fff4;border-bottom:2px solid #27ae60;">
                    <b style="color:#27ae60;">✨ Tailored CV Bullets for this role:</b><br>
                    <div style="font-size:13px;color:#2c3e50;margin-top:4px;">{job['tailored_bullets']}</div>
                </td>
            </tr>"""

        rows += f"""
        <tr>
            <td style="padding:10px;border-bottom:1px solid #eee;font-weight:bold;color:{score_color};">{job['score']}</td>
            <td style="padding:10px;border-bottom:1px solid #eee;">{job['title']}</td>
            <td style="padding:10px;border-bottom:1px solid #eee;">{job['company']}</td>
            <td style="padding:10px;border-bottom:1px solid #eee;">{job['yoe']}</td>
            <td style="padding:10px;border-bottom:1px solid #eee;font-size:13px;color:#555;">{job['reason']}</td>
            <td style="padding:10px;border-bottom:1px solid #eee;">
                <a href="{job['job_url']}" style="background:#0a66c2;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">Apply</a>
            </td>
        </tr>{tailor_html}"""

    sheets_note = ""
    if SHEET_ID:
        sheets_note = f'<p style="font-size:12px;color:#555;">📊 All jobs exported to <a href="https://docs.google.com/spreadsheets/d/{SHEET_ID}">your tracking sheet</a> — mark Applied when done!</p>'

    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:900px;margin:auto;">
        <h2 style="color:#2c3e50;">🎯 LinkedIn Job Sniper — Daily Report</h2>
        <p><b>{len(top_jobs)}</b> roles scored ≥{SCORE_THRESHOLD} today · ✨ = tailored CV bullets included</p>
        {sheets_note}
        <table style="border-collapse:collapse;width:100%;">
            <tr style="background:#f8f9fa;">
                <th style="padding:10px;border-bottom:2px solid #ddd;text-align:left;">Score</th>
                <th style="padding:10px;border-bottom:2px solid #ddd;text-align:left;">Title</th>
                <th style="padding:10px;border-bottom:2px solid #ddd;text-align:left;">Company</th>
                <th style="padding:10px;border-bottom:2px solid #ddd;text-align:left;">YoE</th>
                <th style="padding:10px;border-bottom:2px solid #ddd;text-align:left;">Why a Match</th>
                <th style="padding:10px;border-bottom:2px solid #ddd;text-align:left;">Link</th>
            </tr>{rows}
        </table>
        <p style="margin-top:20px;font-size:11px;color:#aaa;">Powered by LinkedIn Job Sniper · LangChain · Groq</p>
    </body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From']    = sender
    msg['To']      = receiver
    msg.attach(MIMEText(html, 'html'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"Email sent to {receiver}")
    except Exception as e:
        print(f"Email failed: {e}")

# ── Main ──────────────────────────────────────────────────
def main():
    df = pd.DataFrame()
    for location in LOCATIONS:
        for term in SEARCH_TERMS:
            df = pd.concat([df, get_jobs_data(location, term)], ignore_index=True, sort=False)

    if df.empty:
        print("No jobs found. Check proxy/network.")
        return

    df = df.drop_duplicates(subset=["job_url"]).reset_index(drop=True)
    print(f"\nTotal unique jobs to evaluate: {len(df)}")

    scored_jobs = []
    for _, row in df.iterrows():
        title       = row.get('title', 'Unknown')
        description = row.get('description', '')
        job_url     = row.get('job_url', '')

        if not description or len(str(description)) < 50:
            description = fetch_missing_description(job_url) if job_url else ""

        if len(str(description)) < 50:
            print(f"  Skipping '{title}' — no description")
            continue

        result = evaluate_job(title, description)
        print(f"  [{result['score']:3d}] {title} @ {row.get('company', '?')} | {result['reason'][:60]}")

        if result['score'] >= SCORE_THRESHOLD:
            scored_jobs.append({
                "title":            title,
                "company":          row.get('company', 'Unknown'),
                "job_url":          job_url,
                "score":            result['score'],
                "reason":           result['reason'],
                "yoe":              result['yoe'],
                "tailored_bullets": "",
                "description":      description,
            })

    scored_jobs.sort(key=lambda x: x['score'], reverse=True)
    top_15 = scored_jobs[:15]

    for job in top_15:
        if job['score'] >= TAILOR_THRESHOLD:
            print(f"  ✨ Tailoring CV for: {job['title']} @ {job['company']}")
            job['tailored_bullets'] = tailor_resume_for_job(job['title'], job['description'])

    export_to_sheets(top_15)

    print(f"\n{len(top_15)} jobs above threshold. Sending email...")
    send_email(top_15)

if __name__ == "__main__":
    main()
