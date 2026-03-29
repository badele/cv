#!/usr/bin/env python3
import datetime
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple


GITHUB_LOGIN = "badele"
CACHE_PATH = Path(".cache/github-stars.json")
GRAPHQL_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, privacy: PUBLIC) {
      nodes { nameWithOwner stargazerCount }
      pageInfo { hasNextPage endCursor }
    }
  }
}
""".strip()


def run_gh_graphql(query: str, variables: Dict[str, Optional[str]]) -> Dict[str, object]:
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is None:
            continue
        args.extend(["-F", f"{key}={value}"])

    result = subprocess.run(
        args,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        message = "gh api graphql failed."
        if detail:
            message = f"{message} {detail}"
        raise RuntimeError(message)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Failed to parse JSON from gh api graphql.") from exc


def fetch_user_repos_stars(login: str) -> Tuple[Dict[str, int], int]:
    star_map: Dict[str, int] = {}
    total_stars = 0
    cursor: Optional[str] = None

    while True:
        payload = run_gh_graphql(GRAPHQL_QUERY, {"login": login, "cursor": cursor})
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("Missing data in GraphQL response.")

        user = data.get("user")
        if user is None:
            raise RuntimeError(f"GitHub user not found: {login}.")
        if not isinstance(user, dict):
            raise RuntimeError("Invalid user payload from GraphQL.")

        repos = user.get("repositories")
        if not isinstance(repos, dict):
            raise RuntimeError("Invalid repositories payload from GraphQL.")

        nodes = repos.get("nodes")
        if not isinstance(nodes, list):
            raise RuntimeError("Invalid repositories nodes payload from GraphQL.")

        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = node.get("nameWithOwner")
            count = node.get("stargazerCount")
            if not isinstance(name, str) or not isinstance(count, int):
                raise RuntimeError("Invalid repository data from GraphQL.")
            star_map[name] = count
            total_stars += count

        page_info = repos.get("pageInfo")
        if not isinstance(page_info, dict):
            raise RuntimeError("Invalid pageInfo payload from GraphQL.")
        if page_info.get("hasNextPage") is True:
            cursor = page_info.get("endCursor")
            if not isinstance(cursor, str):
                raise RuntimeError("Missing endCursor for pagination.")
            continue
        break

    return star_map, total_stars


def load_cache(cache_path: Path) -> Tuple[Optional[str], Dict[str, int], Optional[int]]:
    # Load cached stars if the JSON payload is valid.
    if not cache_path.exists():
        return None, {}, None

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, {}, None

    if not isinstance(payload, dict):
        return None, {}, None

    date_value = payload.get("date")
    stars_value = payload.get("stars")
    if not isinstance(date_value, str) or not isinstance(stars_value, dict):
        return None, {}, None

    stars: Dict[str, int] = {}
    for repo, count in stars_value.items():
        if isinstance(repo, str) and isinstance(count, int):
            stars[repo] = count

    total_value = payload.get("total_stars")
    total_stars = total_value if isinstance(total_value, int) else None

    return date_value, stars, total_stars


def save_cache(
    cache_path: Path,
    date_value: str,
    stars: Dict[str, int],
    total_stars: int,
) -> None:
    # Persist daily cache for reuse across multiple runs.
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date_value,
        "stars": dict(sorted(stars.items())),
        "total_stars": total_stars,
    }
    cache_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cache_path = root / CACHE_PATH
    today = datetime.date.today().isoformat()
    cache_date, _, cached_total = load_cache(cache_path)
    force_refresh = os.environ.get("usage_force", "false").lower() == "true"
    use_cache = (
        cache_date == today
        and not force_refresh
        and cached_total is not None
    )

    if use_cache:
        print("Cache is up to date.")
        return 0

    star_map, total_stars = fetch_user_repos_stars(GITHUB_LOGIN)
    save_cache(cache_path, today, star_map, total_stars)
    print(f"Updated cache: {CACHE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
