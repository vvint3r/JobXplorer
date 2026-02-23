"""
Master Job Title — First-Run Prompt & Persistence
══════════════════════════════════════════════════
Prompts the user once for their canonical target role,
persists it to config/master_job_title.json, and silently
loads on subsequent runs.

Usage:
    from job_extraction.master_job_title import ensure_master_job_title
    title = ensure_master_job_title()          # interactive prompt on first run
    title = ensure_master_job_title(reset=True) # force re-prompt
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from pathlib import Path

from paths import MASTER_JOB_TITLE_JSON

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _load() -> dict | None:
    """Load master_job_title.json if it exists."""
    if MASTER_JOB_TITLE_JSON.exists():
        try:
            return json.loads(MASTER_JOB_TITLE_JSON.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.warning("Could not load %s: %s", MASTER_JOB_TITLE_JSON, exc)
    return None


def _save(title: str, data: dict | None = None) -> dict:
    """Persist the master job title to JSON."""
    now = datetime.now(timezone.utc).isoformat()
    if data:
        data["master_job_title"] = title
        data["updated_at"] = now
    else:
        data = {
            "master_job_title": title,
            "created_at": now,
            "updated_at": now,
        }
    MASTER_JOB_TITLE_JSON.parent.mkdir(parents=True, exist_ok=True)
    MASTER_JOB_TITLE_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logging.info("Saved master job title → %s", MASTER_JOB_TITLE_JSON)
    return data


def ensure_master_job_title(reset: bool = False) -> str:
    """
    Return the master job title, prompting the user only on first run.

    Parameters
    ----------
    reset : bool
        If True, re-prompt even if a title already exists (--reset-title).

    Returns
    -------
    str  The master job title string.
    """
    data = _load()

    if data and not reset:
        title = data.get("master_job_title", "").strip()
        if title:
            logging.info("Master job title: %s", title)
            return title

    # Interactive prompt
    print("\n  ╔══════════════════════════════════════════════════╗")
    print("  ║  Master Job Title Configuration                 ║")
    print("  ╠══════════════════════════════════════════════════╣")
    print("  ║  Enter the canonical title that represents      ║")
    print("  ║  your target role. This is used to seed the     ║")
    print("  ║  alignment index via OpenAI research.           ║")
    print("  ║                                                 ║")
    print("  ║  Examples:                                      ║")
    print("  ║   • Sr. Director, Marketing Analytics           ║")
    print("  ║   • Data Science Manager                        ║")
    print("  ║   • VP of Growth & Analytics                    ║")
    print("  ╚══════════════════════════════════════════════════╝\n")

    while True:
        title = input("  Master job title: ").strip()
        if title:
            break
        print("  ⚠  Title cannot be empty. Please try again.")

    _save(title, data)
    return title


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Manage master job title.")
    parser.add_argument(
        "--reset", action="store_true",
        help="Re-prompt for the master job title even if one already exists.",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Print the current master job title and exit.",
    )
    args = parser.parse_args()

    if args.show:
        data = _load()
        if data:
            print(data.get("master_job_title", "(not set)"))
        else:
            print("(not set)")
        return

    title = ensure_master_job_title(reset=args.reset)
    print(f"\n  ✓ Master job title: {title}\n")


if __name__ == "__main__":
    main()
