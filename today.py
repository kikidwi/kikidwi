#!/usr/bin/env python3
"""
today.py
--------
Fetches live GitHub statistics (age, repos, stars, followers, commits,
lines of code) for a user and stamps them into two SVG templates
(light_mode.svg / dark_mode.svg) so they can be embedded in a GitHub
profile README and refreshed automatically by GitHub Actions.

Uses lxml.etree to parse and update SVG elements by their id attributes,
similar to Andrew6rant's approach but adapted for kikidwi's profile.

Env vars required (set as repo secrets, injected by the workflow):
    ACCESS_TOKEN   -> a GitHub Personal Access Token (repo + read:user scopes)
    USER_NAME      -> the GitHub username to report on   (e.g. "kikidwi")
    BIRTHDAY       -> ISO date "YYYY-MM-DD"               (e.g. "2002-12-29")
"""

import os
import datetime
import requests
from lxml import etree
from dateutil import relativedelta

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


def format_plural(unit):
    """Returns 's' if unit != 1, else ''."""
    return 's' if unit != 1 else ''


def daily_readme(birthday_str):
    """
    Returns the length of time since birth as a human string.
    e.g. '23 years, 7 months, 3 days'
    """
    born = datetime.datetime.strptime(birthday_str, "%Y-%m-%d")
    diff = relativedelta.relativedelta(datetime.datetime.today(), born)
    return '{} {}, {} {}, {} {}'.format(
        diff.years, 'year' + format_plural(diff.years),
        diff.months, 'month' + format_plural(diff.months),
        diff.days, 'day' + format_plural(diff.days))


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
        "commits": user["contributionsCollection"]["contributionCalendar"][
            "totalContributions"
        ],
    }


def fetch_contributed_repo_count():
    """Count repos user has contributed to (COLLABORATOR + ORG_MEMBER)."""
    query = """
    query($login: String!) {
      user(login: $login) {
        repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, PULL_REQUEST, ISSUE]) {
          totalCount
        }
      }
    }
    """
    try:
        data = graphql(query, {"login": USER_NAME})
        return data["user"]["repositoriesContributedTo"]["totalCount"]
    except Exception:
        return 0


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
    Clones each repo (bare) into a temp dir and sums
    insertions/deletions authored by USER_NAME via `git log --numstat`.
    """
    import subprocess
    import shutil
    import tempfile

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
                continue
            finally:
                shutil.rmtree(dest, ignore_errors=True)
    return total_add, total_del


def fmt(n):
    """Format number with comma separators."""
    return f"{n:,}"


def find_element_by_id(root, element_id):
    """Find an SVG element by its id attribute using XPath."""
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    results = root.xpath(f'//*[@id="{element_id}"]', namespaces=ns)
    if results:
        return results[0]
    return None


def justify_format(root, element_id, new_text, dots_id=None, dots_length=0):
    """
    Update the text of an SVG element identified by element_id.
    Optionally adjust the dots padding in a sibling element.
    """
    new_text = str(new_text)
    element = find_element_by_id(root, element_id)
    if element is not None:
        element.text = new_text

    # Adjust dot-padding if dots_id is provided
    if dots_id and dots_length > 0:
        dots_element = find_element_by_id(root, dots_id)
        if dots_element is not None:
            just_len = max(1, dots_length - len(new_text))
            dots_element.text = '.' * just_len


def svg_overwrite(filename, values):
    """
    Parse SVG file and update elements with live stats data.
    Uses lxml to find elements by id and replace their text content.
    """
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(filename, parser)
    root = tree.getroot()

    # Update age/uptime
    justify_format(root, 'age_data', values['age_data'], 'uptime_dots', 17)

    # Update GitHub Stats
    justify_format(root, 'repo_data', values['repo_data'], 'repo_dots', 5)
    justify_format(root, 'contrib_data', values['contrib_data'])
    justify_format(root, 'star_data', values['star_data'], 'star_dots', 9)
    justify_format(root, 'commit_data', values['commit_data'], 'commit_dots', 16)
    justify_format(root, 'follower_data', values['follower_data'], 'follower_dots', 5)

    # Update Lines of Code
    justify_format(root, 'loc_data', values['loc_net'])
    justify_format(root, 'loc_add', values['loc_add'])
    justify_format(root, 'loc_del', values['loc_del'])

    tree.write(filename, encoding='UTF-8', xml_declaration=True)


def main():
    import shutil

    age = daily_readme(BIRTHDAY)
    stats = fetch_profile_stats()

    # Get contributed repos count
    contrib_count = fetch_contributed_repo_count()

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
        "contrib_data": fmt(contrib_count),
        "star_data": fmt(stats["stars"]),
        "follower_data": fmt(stats["followers"]),
        "commit_data": fmt(stats["commits"]),
        "loc_add": fmt(added),
        "loc_del": fmt(deleted),
        "loc_net": fmt(added - deleted),
    }

    # Copy templates to root, then overwrite with live data
    shutil.copy("templates/dark_mode.svg", "dark_mode.svg")
    shutil.copy("templates/light_mode.svg", "light_mode.svg")

    svg_overwrite("dark_mode.svg", values)
    svg_overwrite("light_mode.svg", values)

    print("Stats updated:", values)


if __name__ == "__main__":
    main()

