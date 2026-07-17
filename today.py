#!/usr/bin/env python3
"""
today.py
--------
Fetches live GitHub statistics (age, repos, stars, followers, commits,
lines of code) for a user and stamps them into two SVG templates
(light_mode.svg / dark_mode.svg) so they can be embedded in a GitHub
profile README and refreshed automatically by GitHub Actions.

Env vars required (set as repo secrets, injected by the workflow):
    ACCESS_TOKEN   -> a GitHub Personal Access Token (repo + read:user scopes)
    USER_NAME      -> the GitHub username to report on   (e.g. "kikidwi")
    BIRTHDAY       -> ISO date "YYYY-MM-DD"               (e.g. "2002-12-29")
"""

import os
import subprocess
import shutil
import tempfile
import datetime
import requests

GITHUB_API = "https://api.github.com/graphql"
USER_NAME = os.environ.get("USER_NAME", "kikidwi")
BIRTHDAY = os.environ.get("BIRTHDAY", "2002-12-29")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")

HEADERS = {"Authorization": f"bearer {ACCESS_TOKEN}"}


def graphql(query, variables=None):
    resp = requests.post(
        GITHUB_API,
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def calc_age(birthday_str):
    """Returns age as a human string: '23 years, 7 months, 3 days'."""
    born = datetime.date.fromisoformat(birthday_str)
    today = datetime.date.today()

    years = today.year - born.year
    months = today.month - born.month
    days = today.day - born.day

    if days < 0:
        months -= 1
        # days in previous month
        prev_month_last_day = (today.replace(day=1) - datetime.timedelta(days=1)).day
        days += prev_month_last_day
    if months < 0:
        years -= 1
        months += 12

    return f"{years} years, {months} months, {days} days"


def fetch_profile_stats():
    """Basic counts: public repos, followers, stars, total commits."""
    query = """
    query($login: String!) {
      user(login: $login) {
        followers { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                      privacy: PUBLIC) {
          totalCount
          nodes { stargazerCount }
        }
        contributionsCollection {
          contributionCalendar { totalContributions }
        }
      }
    }
    """
    data = graphql(query, {"login": USER_NAME})
    user = data["user"]
    total_stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    return {
        "repos": user["repositories"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "stars": total_stars,
        "commits_this_year": user["contributionsCollection"]["contributionCalendar"][
            "totalContributions"
        ],
    }


def fetch_repo_names():
    """All non-fork public repo names owned by the user (for LOC counting)."""
    query = """
    query($login: String!, $after: String) {
      user(login: $login) {
        repositories(first: 50, after: $after, ownerAffiliations: OWNER,
                      isFork: false, privacy: PUBLIC) {
          pageInfo { hasNextPage endCursor }
          nodes { name url }
        }
      }
    }
    """
    names, after = [], None
    while True:
        data = graphql(query, {"login": USER_NAME, "after": after})
        repos = data["user"]["repositories"]
        names.extend(n["name"] for n in repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]
    return names


def count_lines_of_code(repo_names):
    """
    Clones each repo (bare, shallow-history off) into a temp dir and sums
    insertions/deletions authored by USER_NAME via `git log --numstat`.
    Skips repos that fail to clone (private/renamed/etc).
    """
    total_add, total_del = 0, 0
    with tempfile.TemporaryDirectory() as tmp:
        for name in repo_names:
            url = f"https://{ACCESS_TOKEN}@github.com/{USER_NAME}/{name}.git"
            dest = os.path.join(tmp, name)
            try:
                subprocess.run(
                    ["git", "clone", "--quiet", "--bare", url, dest],
                    check=True,
                    timeout=120,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                out = subprocess.run(
                    [
                        "git", "--git-dir", dest, "log",
                        f"--author={USER_NAME}",
                        "--pretty=tformat:", "--numstat",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                ).stdout
                for line in out.splitlines():
                    parts = line.split("\t")
                    if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                        total_add += int(parts[0])
                        total_del += int(parts[1])
            except Exception:
                # Repo unreachable / empty / binary-only diff -> skip quietly
                continue
            finally:
                shutil.rmtree(dest, ignore_errors=True)
    return total_add, total_del


def fmt(n):
    return f"{n:,}"


def render_svg(template_path, output_path, values):
    with open(template_path, "r", encoding="utf-8") as f:
        svg = f.read()
    for key, val in values.items():
        svg = svg.replace("{{ " + key + " }}", str(val))
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg)


def main():
    stats = fetch_profile_stats()
    age = calc_age(BIRTHDAY)

    do_loc = os.environ.get("SKIP_LOC", "false").lower() != "true"
    added, deleted = (0, 0)
    if do_loc and ACCESS_TOKEN:
        try:
            names = fetch_repo_names()
            added, deleted = count_lines_of_code(names)
        except Exception as e:
            print(f"LOC counting skipped due to error: {e}")

    values = {
        "age_data": age,
        "repo_data": fmt(stats["repos"]),
        "star_data": fmt(stats["stars"]),
        "follower_data": fmt(stats["followers"]),
        "commit_data": fmt(stats["commits_this_year"]),
        "loc_add": fmt(added),
        "loc_del": fmt(deleted),
        "loc_net": fmt(added - deleted),
    }

    render_svg("templates/light_mode.svg", "light_mode.svg", values)
    render_svg("templates/dark_mode.svg", "dark_mode.svg", values)

    print("Stats updated:", values)


if __name__ == "__main__":
    main()
