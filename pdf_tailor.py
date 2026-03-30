import os
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import fitz  # pymupdf
from dotenv import load_dotenv
from openai import OpenAI


BASE_CV_DIR = Path("/Users/misbah/Downloads/CVs")
TAILORED_DIR = BASE_CV_DIR / "tailored"
LOG_DIR = Path("/Users/misbah/.openclaw/logs")


def _ensure_dirs() -> None:
    TAILORED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _load_client() -> OpenAI:
    # Load env explicitly from project .env (same as main.py)
    project_root = Path(__file__).resolve().parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
    api_key = os.getenv("API_KEY") or ""
    api_base = os.getenv("API_BASE") or ""
    model = os.getenv("LLM_MODEL") or ""
    if not api_key or not api_base or not model:
        raise RuntimeError(
            "Groq/OpenAI client not configured: ensure API_KEY, API_BASE, and LLM_MODEL "
            "are set in .env before running the PDF tailoring module."
        )
    # openai-python 2.x style client
    client = OpenAI(api_key=api_key, base_url=api_base.rstrip("/"))
    return client


def _list_original_cvs() -> List[Path]:
    if not BASE_CV_DIR.exists():
        return []
    cvs: List[Path] = []
    for p in BASE_CV_DIR.rglob("*.pdf"):
        # Skip anything already under /tailored/
        if TAILORED_DIR in p.parents:
            continue
        cvs.append(p)
    return sorted(cvs)


def _extract_pdf_text(path: Path) -> str:
    text_parts: List[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    return "\n".join(text_parts)


def _tokenise(s: str) -> List[str]:
    return re.findall(r"[A-Za-z]+", s.lower())


def score_cv_for_job(cv_text: str, job_title: str, job_description: str) -> float:
    """
    Very simple local relevance score based on token overlap.
    Does NOT send any data off-machine.
    """
    job_tokens = set(_tokenise(job_title + " " + job_description))
    if not job_tokens:
        return 0.0
    cv_tokens = set(_tokenise(cv_text))
    overlap = job_tokens & cv_tokens
    return len(overlap) / len(job_tokens)


def select_best_cv(
    cvs: List[Tuple[Path, str]],
    job_title: str,
    job_description: str,
) -> Optional[Tuple[Path, str, float]]:
    best: Optional[Tuple[Path, str, float]] = None
    for path, text in cvs:
        score = score_cv_for_job(text, job_title, job_description)
        if best is None or score > best[2]:
            best = (path, text, score)
    return best


def generate_tailored_bullets(
    job_title: str,
    company: str,
    job_description: str,
    cv_text: str,
) -> str:
    """
    Offline fallback: select up to three of the strongest existing bullets from the CV
    (by simple keyword overlap with the job description) and rewrite them into a
    Google XYZ-style sentence without calling any external API.
    """
    # Collect bullet-style lines from the CV text
    bullet_lines: List[str] = []
    for line in cv_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "•", "*")) and len(stripped) > 10:
            bullet_lines.append(stripped.lstrip("-•* ").strip())

    if not bullet_lines:
        return ""

    job_tokens = set(_tokenise(job_title + " " + job_description))

    def score_line(line: str) -> int:
        return len(job_tokens & set(_tokenise(line)))

    # Rank bullets by relevance to the job description
    ranked = sorted(bullet_lines, key=score_line, reverse=True)
    top_lines = [ln for ln in ranked if score_line(ln) > 0][:3] or ranked[:3]

    rewritten: List[str] = []
    for original in top_lines:
        # Very lightweight heuristic split around "by" if present
        parts = re.split(r"\bby\b", original, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            x_part = parts[0].strip(" -–—:;,.")
            y_part = parts[1].strip(" -–—:;,.")
        else:
            x_part = original.strip(" -–—:;,.")
            y_part = "delivering responsibilities closely aligned with the role"

        sentence = (
            f"Accomplished {x_part} by {y_part}, "
            f"resulting in stronger outcomes for the organisation."
        )
        rewritten.append(f"- {sentence}")

    return "\n".join(rewritten)


def _write_tailored_pdf(
    original: Path,
    output: Path,
    job_title: str,
    company: str,
    bullets: str,
) -> None:
    """
    Create a new PDF that preserves the original CV content but
    prepends a new first page containing the tailored bullets.
    The original CV pages remain untouched after that page.
    """
    # Extract original text once so that personal details, dates,
    # companies, and job titles are all preserved verbatim.
    original_text = _extract_pdf_text(original)

    doc_new = fitz.open()
    page = doc_new.new_page()

    heading = f"Tailored CV bullets for {job_title} at {company}\n\n"
    body = heading + bullets + "\n\nOriginal CV:\n" + original_text
    rect = fitz.Rect(40, 40, 550, 800)
    page.insert_textbox(rect, body, fontsize=11, fontname="helv")

    with fitz.open(original) as orig_doc:
        doc_new.insert_pdf(orig_doc)

    doc_new.save(output)
    doc_new.close()


def _sanitise_for_filename(value: str) -> str:
    value = re.sub(r"[^\w]+", "_", value.strip())
    return value.strip("_") or "Unknown"


def tailor_cv_for_job(job: Dict[str, Any]) -> Optional[Path]:
    """
    Tailor a CV for a single job dict with at least:
      - title
      - company
      - description
      - score

    Returns the path to the tailored PDF, or None if nothing was produced.
    """
    _ensure_dirs()

    title = str(job.get("title") or "").strip()
    company = str(job.get("company") or "").strip()
    description = str(job.get("description") or "").strip()

    if not title or not company or not description:
        return None

    cvs_paths = _list_original_cvs()
    if not cvs_paths:
        return None

    # Preload CV texts once per run
    cvs_with_text: List[Tuple[Path, str]] = [
        (p, _extract_pdf_text(p)) for p in cvs_paths
    ]

    best = select_best_cv(cvs_with_text, title, description)
    if not best:
        return None

    best_path, best_text, relevance = best

    # Use offline tailoring (no external API calls) to avoid rate limits.
    bullets = generate_tailored_bullets(
        job_title=title,
        company=company,
        job_description=description,
        cv_text=best_text,
    )
    if not bullets:
        return None

    # Build output filename
    today = date.today().strftime("%Y-%m-%d")
    company_part = _sanitise_for_filename(company)
    title_part = _sanitise_for_filename(title)
    output_name = f"{company_part}_{title_part}_{today}.pdf"
    output_path = TAILORED_DIR / output_name

    _write_tailored_pdf(
        original=best_path,
        output=output_path,
        job_title=title,
        company=company,
        bullets=bullets,
    )

    # Log a concise audit line
    log_line = (
        f"{date.today().isoformat()} | tailored | "
        f"job='{title}' @ '{company}' | score={job.get('score')} | "
        f"source_cv='{best_path.name}' | output='{output_path}' | "
        f"relevance={relevance:.3f}"
    )
    (LOG_DIR / "pdf_tailor.log").open("a", encoding="utf-8").write(log_line + "\n")

    return output_path

