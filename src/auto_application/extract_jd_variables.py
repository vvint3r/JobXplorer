"""
Extract job-description variables to optimize the base resume.

Supports LLM-powered extraction (OpenAI) with a KeyBERT fallback.
Outputs a markdown file per job with incremental IDs and metadata.
"""

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

OUTPUT_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / "data" / "variables_extracted"
DEFAULT_MODEL = "gpt-4o-mini"


# -----------------------------
# Helpers
# -----------------------------
def sanitize(text: str) -> str:
    """Filesystem-friendly token."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "job"


def next_file_id(output_dir: Path) -> int:
    """Find the next numeric ID based on existing files."""
    existing = []
    for f in output_dir.glob("*.md"):
        m = re.match(r"(\d+)_", f.name)
        if m:
            existing.append(int(m.group(1)))
    return (max(existing) if existing else 0) + 1


def read_description_from_csv(csv_path: Path, row: int, column: Optional[str]) -> str:
    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError("CSV is empty.")

    if row >= len(df) or row < 0:
        raise IndexError(f"Row {row} out of range; CSV has {len(df)} rows.")

    candidate_cols = [column] if column else []
    candidate_cols += ["job_description", "description", "jd", "full_text"]

    for col in candidate_cols:
        if col and col in df.columns:
            val = df.iloc[row][col]
            if isinstance(val, str) and val.strip():
                return val

    raise ValueError(f"Could not find a non-empty description column in {candidate_cols}.")


def load_description(args: argparse.Namespace) -> str:
    if args.description_text:
        return args.description_text

    if args.description_file:
        path = Path(args.description_file)
        if not path.exists():
            raise FileNotFoundError(f"Description file not found: {path}")
        return path.read_text(encoding="utf-8")

    if args.source_csv:
        return read_description_from_csv(Path(args.source_csv), args.row, args.description_column)

    raise ValueError("No description provided. Use --description_text, --description_file, or --source_csv.")


# -----------------------------
# Extraction methods
# -----------------------------
def extract_with_llm(description: str, job_title: str, company: str, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    try:
        from openai import OpenAI  # Imported lazily to avoid hard dependency if unused

        client = OpenAI()
        prompt = (
            "You are extracting variables from a job description to optimize a resume. "
            "Use the provided label schema:\n"
            "- Content Type: Conceptual (C), Methodological (M), Technical (T), Operational (O), Tactical (Ta)\n"
            "- Info Architecture: Theory (TH), Methodology (MT), Framework (FR), Process (PR), Technique (TC), Tool (TL), Metric (ME), Model (MO)\n"
            "- Skills: Hard (HS), Soft (SS), Cognitive (CG), Domain Knowledge (DK)\n"
            "- Competency Level: Awareness, Knowledge, Skill, Mastery\n"
            "- Problem Types: Diagnostic (DG), Optimization (OP), Troubleshooting (TS), Innovation (IN), Prevention (PV)\n"
            "- Solution Approaches: Approach (AC), Strategy (ST), Tactic (TA), Heuristic (HE), Algorithm (AL)\n"
            "Return a concise JSON object with arrays for each category, a 'top_requirements' list, and a one-paragraph 'role_focus_summary'. "
            "Keep entries short and specific to the description."
        )

        messages = [
            {"role": "system", "content": "You extract structured variables from job descriptions for resume optimization."},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "job_title": job_title,
                        "company": company,
                        "description": description,
                        "instructions": prompt,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        raise RuntimeError(f"LLM extraction failed: {e}")


def extract_with_keybert(description: str, top_n: int = 15) -> Dict[str, Any]:
    from keybert import KeyBERT  # Imported lazily

    kw_model = KeyBERT()
    keywords = [kw for kw, _ in kw_model.extract_keywords(description, keyphrase_ngram_range=(1, 2), stop_words="english", top_n=top_n)]

    return {
        "content_types": [],
        "info_architecture": [],
        "skills": [],
        "competencies": [],
        "problem_types": [],
        "solution_approaches": [],
        "top_requirements": keywords,
        "role_focus_summary": "Extracted via keyword relevance (no LLM available).",
    }


# -----------------------------
# Rendering
# -----------------------------
def render_markdown(
    job_title: str,
    company: str,
    description_source: str,
    extraction: Dict[str, Any],
    run_method: str,
) -> str:
    today = datetime.now().strftime("%Y-%m-%d")

    def section(title: str, items: Any) -> str:
        if not items:
            return f"### {title}\n- (none)\n"
        if isinstance(items, str):
            items = [items]
        return f"### {title}\n" + "\n".join(f"- {item}" for item in items) + "\n"

    lines = [
        f"# JD Variables – {job_title} @ {company}",
        "",
        "## Metadata",
        f"- job_title: {job_title}",
        f"- company: {company}",
        f"- date_extracted: {today}",
        f"- source: {description_source}",
        f"- method: {run_method}",
        "",
        "## Extracted Variables",
        section("Content Type Labels (C/M/T/O/Ta)", extraction.get("content_types")),
        section("Information Architecture (TH/MT/FR/PR/TC/TL/ME/MO)", extraction.get("info_architecture")),
        section("Skills & Competencies (HS/SS/CG/DK + levels)", extraction.get("skills") or extraction.get("competencies")),
        section("Problem Types (DG/OP/TS/IN/PV)", extraction.get("problem_types")),
        section("Solution Approaches (AC/ST/TA/HE/AL)", extraction.get("solution_approaches")),
        section("Top Requirements", extraction.get("top_requirements")),
        "### Role Focus Summary",
        extraction.get("role_focus_summary", "(none)"),
        "",
    ]
    return "\n".join(lines)


# -----------------------------
# Main CLI
# -----------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract JD variables for resume optimization.")
    parser.add_argument("--job_title", required=True, help="Job title for metadata and file naming.")
    parser.add_argument("--company", required=True, help="Company name for metadata and file naming.")
    parser.add_argument("--description_text", help="Raw job description text.")
    parser.add_argument("--description_file", help="Path to a text/markdown file containing the job description.")
    parser.add_argument("--source_csv", help="Path to a CSV containing job descriptions.")
    parser.add_argument("--row", type=int, default=0, help="Row index to read from CSV (default: 0).")
    parser.add_argument("--description_column", help="Column name in CSV to read (falls back to common names).")
    parser.add_argument("--use_llm", action="store_true", help="Use OpenAI for extraction (requires OPENAI_API_KEY).")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenAI model to use (default: {DEFAULT_MODEL}).")
    return parser.parse_args()


def main():
    args = parse_args()
    description = load_description(args)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_id = next_file_id(OUTPUT_DIR)
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{file_id:03d}_{sanitize(args.company)}_{sanitize(args.job_title)}_{date_str}.md"
    out_path = OUTPUT_DIR / filename

    extraction = {}
    method_used = "keybert_fallback"

    if args.use_llm:
        try:
            extraction = extract_with_llm(description, args.job_title, args.company, model=args.model)
            method_used = "openai_llm"
        except Exception as e:
            print(f"[warn] LLM extraction failed ({e}); falling back to KeyBERT.")

    if not extraction:
        extraction = extract_with_keybert(description)

    md = render_markdown(
        job_title=args.job_title,
        company=args.company,
        description_source=args.description_file or args.source_csv or "provided text",
        extraction=extraction,
        run_method=method_used,
    )

    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote variables to {out_path}")


if __name__ == "__main__":
    main()

