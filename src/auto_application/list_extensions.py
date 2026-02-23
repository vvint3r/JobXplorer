#!/usr/bin/env python3
"""List Chrome extension IDs installed in a user-data-dir."""
import argparse
import glob
import os
from pathlib import Path


def _list_extensions(user_data_dir):
    found = {}
    patterns = [
        os.path.join(user_data_dir, "Default", "Extensions", "*"),
        os.path.join(user_data_dir, "Profile *", "Extensions", "*"),
    ]
    for pattern in patterns:
        for ext_dir in glob.glob(pattern):
            if not os.path.isdir(ext_dir):
                continue
            ext_id = Path(ext_dir).name
            versions = sorted(
                [p.name for p in Path(ext_dir).iterdir() if p.is_dir()],
                reverse=True,
            )
            if ext_id not in found:
                found[ext_id] = versions
    return found


def main():
    parser = argparse.ArgumentParser(description="List Chrome extensions in a user-data-dir.")
    parser.add_argument("--chrome_user_data_dir", required=True, help="Chrome user-data-dir path")
    args = parser.parse_args()

    if not os.path.isdir(args.chrome_user_data_dir):
        raise SystemExit(f"Not a directory: {args.chrome_user_data_dir}")

    extensions = _list_extensions(args.chrome_user_data_dir)
    if not extensions:
        print("No extensions found in this profile.")
        return

    print("Extension IDs found:")
    for ext_id, versions in extensions.items():
        version_str = f" (latest: {versions[0]})" if versions else ""
        print(f"- {ext_id}{version_str}")


if __name__ == "__main__":
    main()
