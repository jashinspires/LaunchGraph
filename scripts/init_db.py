"""
Database Initialization and Seed Script for LaunchGraph.
Creates all schema tables and registers default Workspace and Connection records.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import uuid
from sqlalchemy import select
from launchgraph_core.db.base import Base
from launchgraph_core.db.session import engine, async_session_scope
from launchgraph_core.db.models import Workspace, Connection, AppUser
from launchgraph_core.config import settings

# Fixed UUIDs for predictable local testing
WORKSPACE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SLACK_CONN_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
GITHUB_CONN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
JIRA_CONN_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


async def init_and_seed():
    print(f"[Init] Connecting to database: {settings.DATABASE_URL} ...")

    # 1. Create all schema tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[Init] Schema tables verified and created successfully.")

    # 2. Seed default Workspace and Connections
    async with async_session_scope() as session:
        # Check workspace
        ws_stmt = select(Workspace).where(Workspace.id == WORKSPACE_ID)
        workspace = (await session.execute(ws_stmt)).scalar_one_or_none()
        if not workspace:
            workspace = Workspace(
                id=WORKSPACE_ID,
                slug="launchgraph-hq",
                name="LaunchGraph Engineering HQ",
                tier="production",
                settings={"data_retention_days": 30}
            )
            session.add(workspace)
            print(f"[Init] Created Workspace: '{workspace.name}' (ID: {workspace.id})")

        # Slack Connection
        slack_stmt = select(Connection).where(Connection.id == SLACK_CONN_ID)
        slack_conn = (await session.execute(slack_stmt)).scalar_one_or_none()
        if not slack_conn:
            slack_conn = Connection(
                id=SLACK_CONN_ID,
                workspace_id=WORKSPACE_ID,
                source_type="SLACK",
                status="ACTIVE",
                credentials=b"encrypted-slack-tokens",
                config={
                    "bot_token": settings.SLACK_BOT_TOKEN,
                    "app_token": settings.SLACK_APP_TOKEN,
                    "signing_secret": settings.SLACK_SIGNING_SECRET,
                    "team_id": "T0C89SDQRLM",
                    "app_id": "A0C89TBK8DT",
                }
            )
            session.add(slack_conn)
            print(f"[Init] Created Slack Connection (ID: {slack_conn.id})")
        else:
            # Update tokens if changed
            slack_conn.config = {
                "bot_token": settings.SLACK_BOT_TOKEN,
                "app_token": settings.SLACK_APP_TOKEN,
                "signing_secret": settings.SLACK_SIGNING_SECRET,
                "team_id": "T0C89SDQRLM",
                "app_id": "A0C89TBK8DT",
            }
            print(f"[Init] Updated Slack Connection (ID: {slack_conn.id})")

        # GitHub Connection (Ready for GitHub testing)
        gh_stmt = select(Connection).where(Connection.id == GITHUB_CONN_ID)
        gh_conn = (await session.execute(gh_stmt)).scalar_one_or_none()
        if not gh_conn:
            gh_conn = Connection(
                id=GITHUB_CONN_ID,
                workspace_id=WORKSPACE_ID,
                source_type="GITHUB",
                status="ACTIVE",
                credentials=b"encrypted-gh-token",
                config={
                    "webhook_secret": settings.GITHUB_WEBHOOK_SECRET,
                    "github_token": settings.GITHUB_TOKEN,
                    "repo": settings.GITHUB_REPO
                }
            )
            session.add(gh_conn)
            print(f"[Init] Created GitHub Connection (ID: {gh_conn.id})")
        else:
            gh_conn.config = {
                "webhook_secret": settings.GITHUB_WEBHOOK_SECRET,
                "github_token": settings.GITHUB_TOKEN,
                "repo": settings.GITHUB_REPO
            }
            print(f"[Init] Updated GitHub Connection (ID: {gh_conn.id})")

        # Jira Connection (Ready for Jira testing)
        jira_stmt = select(Connection).where(Connection.id == JIRA_CONN_ID)
        jira_conn = (await session.execute(jira_stmt)).scalar_one_or_none()
        if not jira_conn:
            jira_conn = Connection(
                id=JIRA_CONN_ID,
                workspace_id=WORKSPACE_ID,
                source_type="JIRA",
                status="ACTIVE",
                credentials=b"encrypted-jira-token",
                config={
                    "webhook_secret": settings.JIRA_WEBHOOK_SECRET,
                    "jira_token": settings.JIRA_API_TOKEN,
                    "email": settings.JIRA_EMAIL,
                    "domain": settings.JIRA_DOMAIN or "launchgraph.atlassian.net"
                }
            )
            session.add(jira_conn)
            print(f"[Init] Created Jira Connection (ID: {jira_conn.id})")
        else:
            jira_conn.config = {
                "webhook_secret": settings.JIRA_WEBHOOK_SECRET,
                "jira_token": settings.JIRA_API_TOKEN,
                "email": settings.JIRA_EMAIL,
                "domain": settings.JIRA_DOMAIN or "launchgraph.atlassian.net"
            }
            print(f"[Init] Updated Jira Connection (ID: {jira_conn.id})")

    print("\n[Init Complete] Local environment is ready!")
    print(f"  - Slack Webhook Endpoint:  http://localhost:{settings.INGESTER_PORT}/webhooks/slack/{SLACK_CONN_ID}")
    print(f"  - GitHub Webhook Endpoint: http://localhost:{settings.INGESTER_PORT}/webhooks/github/{GITHUB_CONN_ID}")
    print(f"  - Jira Webhook Endpoint:   http://localhost:{settings.INGESTER_PORT}/webhooks/jira/{JIRA_CONN_ID}")


if __name__ == "__main__":
    asyncio.run(init_and_seed())
