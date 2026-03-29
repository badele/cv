#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path
from typing import Tuple


INDEX_PATH = Path("index.html")
CACHE_PATH = Path(".cache/github-stars.json")
COUNT_PATTERN = re.compile(
    r"(<span[^>]*id=\"github-stars-count\"[^>]*>)(\d+)(</span>)"
)


def load_total_stars(cache_path: Path) -> int:
    if not cache_path.exists():
        raise RuntimeError(f"Missing cache file: {cache_path}.")

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("Invalid JSON cache file.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Invalid cache payload.")

    total_value = payload.get("total_stars")
    if not isinstance(total_value, int):
        raise RuntimeError("Missing total_stars in cache.")

    return total_value


def update_index(text: str, total_stars: int) -> Tuple[str, bool]:
    def replace(match: re.Match) -> str:
        return f"{match.group(1)}{total_stars}{match.group(3)}"

    updated, count = COUNT_PATTERN.subn(replace, text, count=1)
    return updated, count > 0


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    index_path = root / INDEX_PATH
    cache_path = root / CACHE_PATH

    if not index_path.exists():
        sys.stderr.write(f"Missing file: {index_path}\n")
        return 1

    try:
        total_stars = load_total_stars(cache_path)
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    text = index_path.read_text(encoding="utf-8")
    updated, replaced = update_index(text, total_stars)
    if not replaced:
        sys.stderr.write("No github-stars-count element found in index.html.\n")
        return 1

    if updated != text:
        index_path.write_text(updated, encoding="utf-8")
        print(f"Updated: {INDEX_PATH}")
    else:
        print("No updates were necessary.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
