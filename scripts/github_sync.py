"""
LaunchGraph Real-Time GitHub Sync & Watcher.
Uses your GitHub PAT to fetch live Pull Requests and Commits from 'jashinspires/LaunchGraph',
ingests them via Stage 1 Ingestion, and normalizes them into Stage 2 Context Graph.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import uuid
import httpx
from datetime import datetime, timezone
from sqlalchemy import select

from launchgraph_core.config import settings
from launchgraph_core.db.session import async_session_scope
from launchgraph_core.db.models import Connection
from services.ingester.services.event_processor import EventProcessor
from services.normalizer.worker import process_unprocessed_source_events

GITHUB_CONN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def get_headers():
    return {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "LaunchGraph-Sync-Engine"
    }


async def sync_github_events(client: httpx.AsyncClient):
    """Fetches recent pull requests and commits from GitHub and feeds them through LaunchGraph."""
    repo = settings.GITHUB_REPO or "jashinspires/LaunchGraph"
    print(f"\n[GitHub Fetch] Querying live activity for repository: '{repo}' ...")

    # 1. Fetch Pull Requests
    prs_url = f"https://api.github.com/repos/{repo}/pulls?state=all&per_page=10"
    prs_res = await client.get(prs_url, headers=get_headers())
    pulls = prs_res.json() if prs_res.status_code == 200 else []

    # 2. Fetch Recent Commits
    commits_url = f"https://api.github.com/repos/{repo}/commits?per_page=5"
    commits_res = await client.get(commits_url, headers=get_headers())
    commits = commits_res.json() if commits_res.status_code == 200 else []

    print(f"  -> Found {len(pulls)} pull requests, {len(commits)} recent commits.")

    async with async_session_scope() as session:
        conn = (await session.execute(select(Connection).where(Connection.id == GITHUB_CONN_ID))).scalar_one()

        ingested_count = 0

        # Process PRs
        for pr in pulls:
            pr_num = pr.get("number")
            pr_title = pr.get("title", "")
            pr_body = pr.get("body", "")
            pr_action = "closed" if pr.get("state") == "closed" else "opened"
            idempotency_key = f"github:pr-{pr_num}:{pr.get('updated_at')}"
            external_id = f"PR-{pr_num}"

            pr_payload = {
                "action": pr_action,
                "pull_request": pr,
                "repository": {"full_name": repo}
            }

            res = await EventProcessor.process_incoming_webhook(
                session=session,
                connection=conn,
                event_type="pull_request",
                idempotency_key=idempotency_key,
                external_id=external_id,
                raw_payload=pr_payload,
                trust_label="INTERNAL"
            )

            if not res.is_duplicate:
                print(f"  [Stage 1 Ingested] GitHub PR #{pr_num}: '{pr_title}' (SourceEvent: {res.source_event_id})")
                ingested_count += 1

        # Process latest Commits
        for c in commits:
            commit_sha = c.get("sha", "")
            commit_msg = c.get("commit", {}).get("message", "")
            idempotency_key = f"github:commit:{commit_sha[:12]}"
            external_id = f"COMMIT-{commit_sha[:12]}"

            commit_payload = {
                "after": commit_sha,
                "commits": [
                    {
                        "id": commit_sha,
                        "message": commit_msg,
                        "author": c.get("commit", {}).get("author", {})
                    }
                ],
                "repository": {"full_name": repo}
            }

            res = await EventProcessor.process_incoming_webhook(
                session=session,
                connection=conn,
                event_type="push",
                idempotency_key=idempotency_key,
                external_id=external_id,
                raw_payload=commit_payload,
                trust_label="INTERNAL"
            )

            if not res.is_duplicate:
                first_line = commit_msg.split("\n")[0]
                print(f"  [Stage 1 Ingested] Commit {commit_sha[:7]}: '{first_line}' (SourceEvent: {res.source_event_id})")
                ingested_count += 1

        # Normalize any new events
        if ingested_count > 0:
            normalized_count = await process_unprocessed_source_events(session)
            print(f"  [Stage 2 Normalized] {normalized_count} new event(s) attached to Context Graph!")
        else:
            print("  [All Caught Up] No new GitHub events to ingest.")


async def main():
    if not settings.GITHUB_TOKEN:
        print("[Error] GITHUB_TOKEN is not set in .env!")
        return

    print("=" * 80)
    print("  LAUNCHGRAPH REAL-TIME GITHUB TELEMETRY SYNC")
    print("=" * 80)
    print(f"Target Repo: {settings.GITHUB_REPO}")

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Check token validity
        auth_res = await client.get("https://api.github.com/user", headers=get_headers())
        if auth_res.status_code != 200:
            print(f"[Error] GitHub Token authentication failed: {auth_res.status_code} {auth_res.text}")
            return

        user_login = auth_res.json().get("login")
        print(f"[Authenticated] Logged in as: '{user_login}'")

        if "--watch" in sys.argv:
            print("[Watcher Mode] Polling GitHub every 10 seconds for new PRs/commits... (Press Ctrl+C to stop)")
            try:
                while True:
                    await sync_github_events(client)
                    await asyncio.sleep(10)
            except (asyncio.CancelledError, KeyboardInterrupt):
                print("\n[Stopped] GitHub watcher stopped.")
        else:
            await sync_github_events(client)
            print("\nTip: Run 'python scripts/inspect_tables.py' to view the populated context graph!")
            print("Tip: Run 'python scripts/github_sync.py --watch' to keep monitoring continuously in background.")


if __name__ == "__main__":
    asyncio.run(main())
