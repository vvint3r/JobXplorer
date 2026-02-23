#!/usr/bin/env python3
"""
Check basic prerequisites for the pipeline and Simplify-assisted autofill.
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path


def _check_linkedin_cookies(cookie_path):
    if not cookie_path.exists():
        return False, f"LinkedIn cookies not found: {cookie_path}"
    try:
        raw = cookie_path.read_text(encoding="utf-8").strip()
        data = json.loads(raw)
        if not isinstance(data, list) or not data:
            return False, "LinkedIn cookies file is empty or not a list."
        return True, f"LinkedIn cookies OK ({len(data)} cookies)."
    except Exception as exc:
        return False, f"Failed to parse LinkedIn cookies: {exc}"


def _is_extension_installed(user_data_dir, extension_id):
    patterns = [
        os.path.join(user_data_dir, "Default", "Extensions", extension_id),
        os.path.join(user_data_dir, "Profile *", "Extensions", extension_id),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if any(os.path.isdir(path) for path in matches):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Check prerequisites for JobXplore runs.")
    parser.add_argument("--skip_cookies", action="store_true", help="Skip LinkedIn cookies check.")
    parser.add_argument("--cookie_path", type=str, default=None, help="Path to linkedin_cookies.txt")
    parser.add_argument("--check_simplify", action="store_true", help="Check Simplify extension installation.")
    parser.add_argument("--chrome_user_data_dir", type=str, default=None, help="Chrome user-data-dir to check.")
    parser.add_argument("--simplify_extension_id", type=str, default=None, help="Simplify Chrome extension ID.")

    args = parser.parse_args()

    issues = []
    checks = []

    if not args.skip_cookies:
        if args.cookie_path:
            cookie_path = Path(args.cookie_path)
        else:
            cookie_path = Path(__file__).resolve().parents[2] / "config" / "linkedin_cookies.txt"
        ok, msg = _check_linkedin_cookies(cookie_path)
        checks.append(msg)
        if not ok:
            issues.append(msg)

    if args.check_simplify:
        if not args.chrome_user_data_dir or not args.simplify_extension_id:
            issues.append("Simplify check requires --chrome_user_data_dir and --simplify_extension_id.")
        else:
            if _is_extension_installed(args.chrome_user_data_dir, args.simplify_extension_id):
                checks.append("Simplify extension found in Chrome profile.")
            else:
                issues.append("Simplify extension not found in Chrome profile.")

    for line in checks:
        print(line)

    if issues:
        print("\nPrereq check failed:")
        for line in issues:
            print(f"- {line}")
        sys.exit(1)

    print("\nPrereq check passed.")


if __name__ == "__main__":
    main()
