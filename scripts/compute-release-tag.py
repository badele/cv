#!/usr/bin/env python3
import datetime
import os
import re
import subprocess
import sys


def main() -> int:
    release_date = os.environ.get("RELEASE_DATE")
    if not release_date:
        release_date = datetime.datetime.utcnow().strftime("%Y.%m.%d")

    pattern = f"v{release_date}.*"
    result = subprocess.run(
        ["git", "tag", "-l", pattern],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write("Failed to list git tags.\n")
        sys.stderr.write(result.stderr)
        return result.returncode

    counters = []
    for tag in result.stdout.splitlines():
        match = re.fullmatch(rf"v{re.escape(release_date)}\.(\d+)", tag)
        if match:
            counters.append(int(match.group(1)))

    next_counter = (max(counters) if counters else 0) + 1
    release_tag = f"v{release_date}.{next_counter}"

    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"tag={release_tag}\n")

    print(release_tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
