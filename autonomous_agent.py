import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
from dotenv import load_dotenv

from jobspy import scrape_jobs

from main import (
    SEARCH_TERMS,
    LOCATIONS,
    RESULT_LIMIT,
    HOURS_OLD,
    SCORE_THRESHOLD,
    TAILOR_THRESHOLD,
    fetch_missing_description,
    evaluate_job,
)
from pdf_tailor import tailor_cv_for_job


LOG_DIR = Path("/Users/misbah/.openclaw/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
APPLICATIONS_LOG = LOG_DIR / "applications.log"
MAX_APPLICATIONS_PER_DAY = 20


def _applications_today_count() -> int:
    """Count application log entries for today (status prepared/submitted/fail)."""
    today = datetime.now().strftime("%Y-%m-%d")
    if not APPLICATIONS_LOG.exists():
        return 0
    count = 0
    for line in APPLICATIONS_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip() and today in line:
            count += 1
    return count


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [agent] {msg}"
    print(line)
    (LOG_DIR / "agent.log").open("a", encoding="utf-8").write(line + "\n")


def scrape_once() -> pd.DataFrame:
    df = pd.DataFrame()
    for location in LOCATIONS:
        for term in SEARCH_TERMS:
            log(f"scrape start term='{term}' location='{location}'")
            try:
                jobs = scrape_jobs(
                    site_name=["linkedin"],
                    search_term=term,
                    location=location,
                    results_wanted=RESULT_LIMIT,
                    hours_old=HOURS_OLD,
                    proxies=None,
                )
                log(f"scrape done term='{term}' location='{location}' count={len(jobs)}")
                df = pd.concat([df, jobs], ignore_index=True, sort=False)
            except Exception as e:
                log(f"scrape error term='{term}' location='{location}' error={type(e).__name__}")
    if df.empty:
        log("no jobs scraped in this cycle")
        return df
    df = df.drop_duplicates(subset=["job_url"]).reset_index(drop=True)
    log(f"unique jobs to evaluate: {len(df)}")
    return df


def evaluate_jobs(df: pd.DataFrame) -> List[Dict[str, Any]]:
    scored: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        title = row.get("title", "Unknown")
        description = row.get("description", "") or ""
        job_url = row.get("job_url", "") or ""

        if len(str(description)) < 50 and job_url:
            description = fetch_missing_description(job_url) or ""

        if len(str(description)) < 50:
            log(f"skip job (no description) title='{title}'")
            continue

        result = evaluate_job(str(title), str(description))
        score = int(result.get("score", 0) or 0)
        log(
            f"eval score={score:3d} title='{title}' company='{row.get('company', '?')}' "
            f"reason='{str(result.get('reason',''))[:60]}'"
        )
        if score >= SCORE_THRESHOLD:
            scored.append(
                {
                    "title": str(title),
                    "company": str(row.get("company", "Unknown")),
                    "job_url": str(job_url),
                    "score": score,
                    "reason": str(result.get("reason", "")),
                    "yoe": str(result.get("yoe", "")),
                    "description": str(description),
                }
            )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def log_application(
    job: Dict[str, Any],
    cv_path: Optional[Path],
    status: str,
    message: str = "",
) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = job.get("title", "")
    company = job.get("company", "")
    url = job.get("job_url", "")
    score = job.get("score", 0)
    cv_used = str(cv_path) if cv_path else ""
    line = f"{title} | {company} | {url} | {score} | {cv_used} | {ts} | {status}"
    if message:
        line += f" | {message}"
    APPLICATIONS_LOG.open("a", encoding="utf-8").write(line + "\n")


def apply_to_job(job: Dict[str, Any], cv_path: Optional[Path]) -> None:
    """
    Log application attempt. Enforces 20 applications per day.
    LinkedIn Easy Apply would require browser automation (out of scope).
    """
    if _applications_today_count() >= MAX_APPLICATIONS_PER_DAY:
        log(f"skip apply (daily limit {MAX_APPLICATIONS_PER_DAY} reached)")
        return
    note = "Tailored CV ready; manual submit on LinkedIn required."
    log_application(job, cv_path, status="Prepared", message=note)


def run_cycle(max_tailored: Optional[int] = None) -> None:
    df = scrape_once()
    if df.empty:
        return

    scored_jobs = evaluate_jobs(df)
    if not scored_jobs:
        log("no jobs above SCORE_THRESHOLD in this cycle")
        return

    tailored_count = 0
    apps_today = _applications_today_count()
    for job in scored_jobs:
        if job["score"] < TAILOR_THRESHOLD:
            continue
        if apps_today + tailored_count >= MAX_APPLICATIONS_PER_DAY:
            log(f"stop tailoring (daily limit {MAX_APPLICATIONS_PER_DAY} reached)")
            break
        if max_tailored is not None and tailored_count >= max_tailored:
            break
        log(
            f"tailor start title='{job['title']}' company='{job['company']}' "
            f"score={job['score']}"
        )
        try:
            out_path = tailor_cv_for_job(job)
            if out_path:
                log(
                    f"tailor done title='{job['title']}' company='{job['company']}' "
                    f"score={job['score']} pdf='{out_path}'"
                )
                tailored_count += 1
                # Attempt application (logged as prepared)
                apply_to_job(job, out_path)
            else:
                log(
                    f"tailor skipped/no-output title='{job['title']}' "
                    f"company='{job['company']}' score={job['score']}"
                )
        except Exception as e:
            log(
                f"tailor error title='{job['title']}' company='{job['company']}' "
                f"score={job['score']} error={type(e).__name__}"
            )


def main() -> None:
    # Load env for this process explicitly
    project_root = Path(__file__).resolve().parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))

    import argparse

    parser = argparse.ArgumentParser(description="Autonomous LinkedIn Job Sniper agent")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    parser.add_argument(
        "--max-tailored",
        type=int,
        default=None,
        help="Max number of tailored PDFs to generate in this run",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=int,
        default=24 * 3600,
        help="Seconds to sleep between cycles in continuous mode (default: 24h)",
    )
    args = parser.parse_args()

    log(
        f"agent start once={args.once} max_tailored={args.max_tailored} "
        f"sleep_seconds={args.sleep_seconds}"
    )

    if args.once:
        try:
            run_cycle(max_tailored=args.max_tailored)
        except Exception as e:
            log(f"cycle error_once {type(e).__name__}")
        log("agent completed single cycle")
        return

    while True:
        try:
            run_cycle(max_tailored=args.max_tailored)
            # Normal wait between full cycles
            time.sleep(args.sleep_seconds)
        except Exception as e:
            # On any error: log, wait 5 minutes, retry
            log(f"cycle error {type(e).__name__}")
            time.sleep(5 * 60)


if __name__ == "__main__":
    main()

