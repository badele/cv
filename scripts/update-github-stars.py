#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import re
import ssl
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple
from urllib import error, request


DEFAULT_LATEX_FILES = (Path("latex/github.tex"),)
GITHUB_API_BASE = "https://api.github.com/repos"
CACHE_PATH = Path(".cache/github-stars.json")
HREF_PATTERN = re.compile(r"\\href\{https://github.com/([^}]+)\}")
ENTRY_PATTERN = re.compile(
    r"(\\textbf\{)(\d+)(\}\s*\\href\{https://github.com/)([^}]+)(\})"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update GitHub star counts in LaTeX files.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        default=list(DEFAULT_LATEX_FILES),
        help="LaTeX files to update (defaults to latex/github.tex).",
    )
    return parser.parse_args()


def extract_repos(text: str) -> Iterable[str]:
    # Collect unique repo slugs from GitHub hrefs in the LaTeX file.
    return {match.group(1) for match in HREF_PATTERN.finditer(text)}


def fetch_repo_stars(repo: str) -> int:
    # Fetch stargazer count from the public GitHub REST API.
    url = f"{GITHUB_API_BASE}/{repo}"
    req = request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "cv-github-stars-updater",
        },
    )
    try:
        payload = load_payload(req)
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        message = f"GitHub API error {exc.code} for {repo}."
        if details:
            message = f"{message} {details}"
        raise RuntimeError(message) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to reach GitHub API for {repo}.") from exc

    stars = payload.get("stargazers_count")
    if stars is None:
        raise RuntimeError(f"Missing stargazers_count for {repo}.")
    if not isinstance(stars, int):
        raise RuntimeError(f"Invalid stargazers_count for {repo}.")
    return stars


def load_payload(req: request.Request) -> Dict[str, object]:
    # Try the default SSL context; fall back to certifi when needed.
    try:
        with request.urlopen(req, timeout=15) as response:
            return json.load(response)
    except ssl.SSLCertVerificationError as exc:
        return load_payload_with_certifi(req, exc)
    except error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            return load_payload_with_certifi(req, exc.reason)
        raise


def load_payload_with_certifi(
    req: request.Request,
    exc: BaseException,
) -> Dict[str, object]:
    # Retry the request using certifi's CA bundle when system certs fail.
    try:
        import certifi
    except ImportError as certifi_exc:
        raise RuntimeError(
            "SSL verification failed. Install ca-certificates or certifi."
        ) from certifi_exc

    context = ssl.create_default_context(cafile=certifi.where())
    with request.urlopen(req, timeout=15, context=context) as response:
        return json.load(response)


def build_star_map(repos: Iterable[str]) -> Dict[str, int]:
    star_map: Dict[str, int] = {}
    for repo in sorted(repos):
        star_map[repo] = fetch_repo_stars(repo)
    return star_map


def load_cache(cache_path: Path) -> Tuple[Optional[str], Dict[str, int]]:
    # Load cached stars if the JSON payload is valid.
    if not cache_path.exists():
        return None, {}

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, {}

    if not isinstance(payload, dict):
        return None, {}

    date_value = payload.get("date")
    stars_value = payload.get("stars")
    if not isinstance(date_value, str) or not isinstance(stars_value, dict):
        return None, {}

    stars: Dict[str, int] = {}
    for repo, count in stars_value.items():
        if isinstance(repo, str) and isinstance(count, int):
            stars[repo] = count

    return date_value, stars


def save_cache(cache_path: Path, date_value: str, stars: Dict[str, int]) -> None:
    # Persist daily cache for reuse across multiple runs.
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date_value,
        "stars": dict(sorted(stars.items())),
    }
    cache_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def update_text(text: str, stars: Dict[str, int]) -> str:
    # Replace the star count in each matching LaTeX entry.
    def replace(match: re.Match) -> str:
        repo = match.group(4)
        count = stars.get(repo)
        if count is None:
            return match.group(0)
        return f"{match.group(1)}{count}{match.group(3)}{repo}{match.group(5)}"

    return ENTRY_PATTERN.sub(replace, text)


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    cache_path = root / CACHE_PATH

    latex_files = [root / Path(path) for path in args.files]
    for path in latex_files:
        if not path.exists():
            sys.stderr.write(f"Missing file: {path}\n")
            return 1

    texts = {}
    repos = set()
    for path in latex_files:
        text = path.read_text(encoding="utf-8")
        texts[path] = text
        repos.update(extract_repos(text))

    if not repos:
        sys.stderr.write("No GitHub repositories found.\n")
        return 1

    today = datetime.date.today().isoformat()
    cache_date, cached_stars = load_cache(cache_path)
    force_refresh = os.environ.get("usage_force", "false").lower() == "true"
    use_cache = cache_date == today and not force_refresh

    star_map = dict(cached_stars) if use_cache else {}
    missing_repos = sorted(repo for repo in repos if repo not in star_map)
    if missing_repos:
        star_map.update(build_star_map(missing_repos))
        save_cache(cache_path, today, star_map)

    updated_files = []
    for path, text in texts.items():
        updated = update_text(text, star_map)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            updated_files.append(path)

    if updated_files:
        updated_list = ", ".join(str(path.relative_to(root)) for path in updated_files)
        print(f"Updated: {updated_list}")
    else:
        print("No updates were necessary.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
