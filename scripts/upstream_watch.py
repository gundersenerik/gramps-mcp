#!/usr/bin/env python3
# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Report upstream activity in a tracking issue. Never changes any code.

Watches the upstream repository for two things: new commits on its default
branch, and pull requests that were not open the last time this ran. Each
finding is posted as a comment on a single long-lived tracking issue, which
is what produces the GitHub notification.

Nothing is merged, branched or pushed. The issue body doubles as the state
store, so no bookkeeping commits are made either.
"""

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

API_ROOT = "https://api.github.com"
ISSUE_TITLE = "Upstream watch"
ISSUE_LABEL = "upstream-watch"
STATE_RE = re.compile(r"<!-- upstream-watch-state\s*(?P<json>\{.*?\})\s*-->", re.S)


class ApiError(RuntimeError):
    """Raised when the GitHub API returns an unexpected response."""


def run_git(*args: str) -> str:
    """
    Run a git command and return its stripped stdout.

    Args:
        *args (str): Arguments passed to git.

    Returns:
        str: Standard output with surrounding whitespace removed.
    """
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def api_request(
    path: str, token: str, method: str = "GET", payload: Optional[Dict] = None
):
    """
    Call the GitHub REST API.

    Args:
        path (str): Path below the API root, starting with a slash.
        token (str): Token used for the Authorization header.
        method (str): HTTP method to use.
        payload (Optional[Dict]): JSON body for write requests.

    Returns:
        object: The decoded JSON response.
    """
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(f"{API_ROOT}{path}", data=data, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:400]
        raise ApiError(f"{method} {path} returned {error.code}: {detail}") from error


def fetch_upstream(url: str, branch: str) -> str:
    """
    Make the upstream branch available locally and return its commit.

    Args:
        url (str): Clone URL of the upstream repository.
        branch (str): Upstream branch to fetch.

    Returns:
        str: The upstream branch head commit SHA.
    """
    remotes = run_git("remote").split()
    if "upstream" not in remotes:
        run_git("remote", "add", "upstream", url)
    run_git("fetch", "--quiet", "upstream", branch)
    return run_git("rev-parse", "FETCH_HEAD")


def commits_ahead(local_ref: str) -> List[Tuple[str, str, str, str]]:
    """
    List upstream commits that this fork's branch does not contain.

    Args:
        local_ref (str): The local branch to compare against.

    Returns:
        List[Tuple[str, str, str, str]]: Short SHA, subject, author and date.
    """
    output = run_git(
        "log",
        "--no-merges",
        "--format=%h%x1f%s%x1f%an%x1f%ad",
        "--date=short",
        f"{local_ref}..FETCH_HEAD",
    )
    if not output:
        return []
    rows = []
    for line in output.split("\n"):
        parts = line.split("\x1f")
        if len(parts) == 4:
            rows.append((parts[0], parts[1], parts[2], parts[3]))
    return rows


def read_state(body: str) -> Dict:
    """
    Extract the stored watch state from an issue body.

    Args:
        body (str): The tracking issue body.

    Returns:
        Dict: Stored state, or an empty baseline when none is present.
    """
    match = STATE_RE.search(body or "")
    if not match:
        return {"upstream_sha": "", "known_prs": []}
    try:
        return json.loads(match.group("json"))
    except json.JSONDecodeError:
        return {"upstream_sha": "", "known_prs": []}


def render_body(upstream: str, sha: str, prs: List[Dict]) -> str:
    """
    Build the tracking issue body, including the embedded state block.

    Args:
        upstream (str): Upstream repository in owner/name form.
        sha (str): Upstream branch head commit SHA.
        prs (List[Dict]): Currently open upstream pull requests.

    Returns:
        str: Markdown body for the tracking issue.
    """
    state = json.dumps(
        {"upstream_sha": sha, "known_prs": sorted(p["number"] for p in prs)}
    )
    lines = [
        f"Watching [{upstream}](https://github.com/{upstream}) for new commits "
        "and new pull requests.",
        "",
        "Findings are posted as comments on this issue. Nothing in this fork is "
        "changed automatically: no branches, no merges, no pull requests.",
        "",
        f"Last seen upstream commit: `{sha[:12]}`",
        f"Open upstream pull requests: {len(prs)}",
        "",
        f"<!-- upstream-watch-state {state} -->",
    ]
    return "\n".join(lines)


def commit_comment(upstream: str, rows: List[Tuple[str, str, str, str]]) -> str:
    """
    Render the notification for new upstream commits.

    Args:
        upstream (str): Upstream repository in owner/name form.
        rows (List[Tuple[str, str, str, str]]): Commits to report.

    Returns:
        str: Markdown comment body.
    """
    lines = [
        f"## Upstream main moved ({len(rows)} new commit(s))",
        "",
        "| Commit | Subject | Author | Date |",
        "| --- | --- | --- | --- |",
    ]
    for sha, subject, author, date in rows:
        link = f"[`{sha}`](https://github.com/{upstream}/commit/{sha})"
        lines.append(f"| {link} | {subject} | {author} | {date} |")
    lines += ["", "Nothing was merged. Ask if you want these brought in."]
    return "\n".join(lines)


def pr_comment(upstream: str, prs: List[Dict]) -> str:
    """
    Render the notification for pull requests seen for the first time.

    Args:
        upstream (str): Upstream repository in owner/name form.
        prs (List[Dict]): Newly seen pull requests.

    Returns:
        str: Markdown comment body.
    """
    lines = [f"## New upstream pull request(s): {len(prs)}", ""]
    for pull in prs:
        lines.append(
            f"- [#{pull['number']}]({pull['html_url']}) {pull['title']} "
            f"(by {pull['user']['login']}, opened {pull['created_at'][:10]})"
        )
    lines += ["", "These are proposals upstream, not merged there or here."]
    return "\n".join(lines)


def find_issue(fork: str, token: str) -> Optional[Dict]:
    """
    Locate the existing tracking issue, if one has been opened.

    Args:
        fork (str): This repository in owner/name form.
        token (str): GitHub token.

    Returns:
        Optional[Dict]: The issue payload, or None when absent.
    """
    issues = api_request(
        f"/repos/{fork}/issues?state=all&labels={ISSUE_LABEL}&per_page=100", token
    )
    for issue in issues:
        if issue.get("title") == ISSUE_TITLE:
            return issue
    return None


def main() -> int:
    """
    Compare the fork against upstream and report anything new.

    Returns:
        int: Process exit status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, help="Upstream owner/name")
    parser.add_argument("--branch", default="main", help="Upstream branch to watch")
    parser.add_argument("--local-ref", default="origin/main", help="Fork branch")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print findings without posting"
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    fork = os.environ.get("GITHUB_REPOSITORY", "")
    if not args.dry_run and not (token and fork):
        parser.error("GITHUB_TOKEN and GITHUB_REPOSITORY are required")

    sha = fetch_upstream(f"https://github.com/{args.upstream}", args.branch)
    rows = commits_ahead(args.local_ref)
    prs = api_request(f"/repos/{args.upstream}/pulls?state=open&per_page=100", token)

    issue = find_issue(fork, token) if not args.dry_run else None
    first_run = issue is None
    state = read_state(issue.get("body", "") if issue else "")

    new_prs = [p for p in prs if p["number"] not in set(state.get("known_prs", []))]
    commits_are_new = bool(rows) and sha != state.get("upstream_sha", "")

    comments = []
    if first_run:
        # Seed the baseline instead of announcing every pull request that was
        # already open when the watch started.
        comments.append(
            "Upstream watch started. Future comments here will report new "
            "commits on upstream main and pull requests opened after now."
        )
    else:
        if commits_are_new:
            comments.append(commit_comment(args.upstream, rows))
        if new_prs:
            comments.append(pr_comment(args.upstream, new_prs))

    body = render_body(args.upstream, sha, prs)

    if args.dry_run:
        print(f"upstream {args.upstream}@{args.branch} = {sha[:12]}")
        print(f"commits ahead of {args.local_ref}: {len(rows)}")
        print(f"open upstream pull requests: {len(prs)}")
        for comment in comments:
            print("\n--- would comment ---\n" + comment)
        if not comments:
            print("\nnothing new to report")
        return 0

    if issue is None:
        issue = api_request(
            f"/repos/{fork}/issues",
            token,
            "POST",
            {"title": ISSUE_TITLE, "body": body, "labels": [ISSUE_LABEL]},
        )
    else:
        api_request(
            f"/repos/{fork}/issues/{issue['number']}", token, "PATCH", {"body": body}
        )

    for comment in comments:
        api_request(
            f"/repos/{fork}/issues/{issue['number']}/comments",
            token,
            "POST",
            {"body": comment},
        )
    print(f"reported {len(comments)} update(s) on issue #{issue['number']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
