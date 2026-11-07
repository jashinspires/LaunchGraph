"""
LaunchGraph Real-Time Jira Cloud Sync & Watcher.
Uses your Jira API Token and Domain to fetch live issues from your Jira workspace,
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

JIRA_CONN_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


def get_jira_auth():
    return (settings.JIRA_EMAIL or "", settings.JIRA_API_TOKEN or "")


async def test_jira_connection():
    domain = (settings.JIRA_DOMAIN or "").replace("https://", "").replace("http://", "").strip("/")
    if not domain or "your-jira-domain" in domain:
        print("[Notice] Please set your real Jira Domain in .env (e.g., JIRA_DOMAIN=myteam.atlassian.net)")
        return False

    auth = get_jira_auth()
    if not auth[0] or not auth[1]:
        print("[Notice] JIRA_EMAIL and JIRA_API_TOKEN are required in .env")
        return False

    url = f"https://{domain}/rest/api/3/myself"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get(url, auth=auth)
            if res.status_code == 200:
                data = res.json()
                print(f"[Authenticated] Connected to Jira Cloud ({domain}) as '{data.get('displayName')}' ({data.get('emailAddress')})")
                return True
            else:
                print(f"[Auth Error] Jira returned {res.status_code}: {res.text[:200]}")
                return False
        except Exception as exc:
            print(f"[Connection Error] Could not connect to {url}: {exc}")
            return False


async def sync_jira_issues():
    domain = (settings.JIRA_DOMAIN or "").replace("https://", "").replace("http://", "").strip("/")
    auth = get_jira_auth()

    url = f"https://{domain}/rest/api/3/search?jql=order by updated DESC&maxResults=10"
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(url, auth=auth)
        if res.status_code != 200:
            print(f"[Error] Failed to fetch Jira issues: {res.status_code} {res.text[:200]}")
            return

        issues = res.json().get("issues", [])
        print(f"\n[Jira Fetch] Found {len(issues)} issues in Jira workspace '{domain}'...")

        async with async_session_scope() as session:
            conn = (await session.execute(select(Connection).where(Connection.id == JIRA_CONN_ID))).scalar_one()
            ingested_count = 0

            for issue in issues:
                issue_id = issue.get("id")
                issue_key = issue.get("key")
                fields = issue.get("fields", {})
                summary = fields.get("summary", "")
                updated = fields.get("updated", "")
                status_name = fields.get("status", {}).get("name", "Unknown")

                idempotency_key = f"jira:{issue_id}:{updated}"
                external_id = f"JIRA:{issue_key}"

                payload = {
                    "webhookEvent": "jira:issue_updated",
                    "timestamp": int(datetime.now(timezone.utc).timestamp()),
                    "issue": issue
                }

                result = await EventProcessor.process_incoming_webhook(
                    session=session,
                    connection=conn,
                    event_type="jira:issue_updated",
                    idempotency_key=idempotency_key,
                    external_id=external_id,
                    raw_payload=payload,
                    trust_label="INTERNAL"
                )

                if not result.is_duplicate:
                    print(f"  [Stage 1 Ingested] Jira Ticket {issue_key}: '{summary}' [{status_name}] (SourceEvent: {result.source_event_id})")
                    ingested_count += 1

            if ingested_count > 0:
                normalized = await process_unprocessed_source_events(session)
                print(f"  [Stage 2 Normalized] {normalized} Jira event(s) anchored into Context Graph!")
            else:
                print("  [All Caught Up] No new Jira updates to ingest.")


async def main():
    print("=" * 80)
    print("  LAUNCHGRAPH REAL-TIME JIRA CLOUD TELEMETRY SYNC")
    print("=" * 80)

    is_ok = await test_jira_connection()
    if is_ok:
        await sync_jira_issues()
        print("\nTip: Run 'python scripts/inspect_tables.py' to view the anchored Context Graph!")


if __name__ == "__main__":
    asyncio.run(main())
