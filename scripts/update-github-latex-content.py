#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path
from typing import Dict, Tuple


LATEX_PATH = Path("latex/github.tex")
CACHE_PATH = Path(".cache/github-stars.json")
ENTRY_PATTERN = re.compile(
    r"(\\textbf\{)(\d+)(\}\s*\\href\{https://github.com/)([^}]+)(\})"
)
TOTAL_PATTERN = re.compile(r"(\\textbf\{)(\d+)(\}\s*Total GitHub stars)")


def load_cache(cache_path: Path) -> Tuple[Dict[str, int], int]:
    if not cache_path.exists():
        raise RuntimeError(f"Missing cache file: {cache_path}.")

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("Invalid JSON cache file.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Invalid cache payload.")

    stars_value = payload.get("stars")
    if not isinstance(stars_value, dict):
        raise RuntimeError("Missing stars map in cache.")

    total_value = payload.get("total_stars")
    if not isinstance(total_value, int):
        raise RuntimeError("Missing total_stars in cache.")

    stars: Dict[str, int] = {}
    for repo, count in stars_value.items():
        if isinstance(repo, str) and isinstance(count, int):
            stars[repo] = count

    return stars, total_value


def update_text(text: str, stars: Dict[str, int], total_stars: int) -> str:
    # Replace the star count in each matching LaTeX entry.
    def replace(match: re.Match) -> str:
        repo = match.group(4)
        count = stars.get(repo)
        if count is None:
            return match.group(0)
        return f"{match.group(1)}{count}{match.group(3)}{repo}{match.group(5)}"

    updated = ENTRY_PATTERN.sub(replace, text)

    def replace_total(match: re.Match) -> str:
        return f"{match.group(1)}{total_stars}{match.group(3)}"

    return TOTAL_PATTERN.sub(replace_total, updated)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    latex_path = root / LATEX_PATH
    cache_path = root / CACHE_PATH

    if not latex_path.exists():
        sys.stderr.write(f"Missing file: {latex_path}\n")
        return 1

    try:
        stars, total_stars = load_cache(cache_path)
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    text = latex_path.read_text(encoding="utf-8")
    updated = update_text(text, stars, total_stars)
    if updated != text:
        latex_path.write_text(updated, encoding="utf-8")
        print(f"Updated: {LATEX_PATH}")
    else:
        print("No updates were necessary.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
