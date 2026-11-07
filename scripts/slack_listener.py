"""
Real-Time Slack Socket Mode Ingestion Listener for LaunchGraph.
Connects directly to your Slack Workspace via WebSocket (no ngrok / public URL needed).
Listens for live messages, ingests them via Stage 1 Ingestion, and triggers Stage 2 Normalization.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import uuid
import time
from sqlalchemy import select
from slack_sdk.socket_mode.builtin import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from launchgraph_core.config import settings
from launchgraph_core.db.session import async_session_scope
from launchgraph_core.db.models import Connection
from services.ingester.services.event_processor import EventProcessor
from services.normalizer.worker import process_unprocessed_source_events

SLACK_CONN_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


async def handle_slack_event_async(payload: dict):
    """Processes inbound Slack Events API payload through LaunchGraph Ingestion + Normalization."""
    event = payload.get("event", {})
    text = event.get("text", "")
    channel = event.get("channel", "unknown")
    user = event.get("user", "unknown")
    ts = event.get("ts", str(time.time()))
    event_id = payload.get("event_id", str(uuid.uuid4()))

    print(f"\n[Slack Ingress] Received message from user '{user}' in channel '{channel}':")
    print(f"  Text: \"{text}\"")

    async with async_session_scope() as session:
        # Fetch connection
        stmt = select(Connection).where(Connection.id == SLACK_CONN_ID)
        conn = (await session.execute(stmt)).scalar_one_or_none()
        if not conn:
            print("[Error] Slack Connection (22222222-...) not found in database. Run 'python scripts/init_db.py' first.")
            return

        idempotency_key = f"slack:{event_id}"
        external_id = f"SLACK:{channel}:{ts}"

        # 1. Stage 1: Ingestion (deduplication + secret scrubbing)
        result = await EventProcessor.process_incoming_webhook(
            session=session,
            connection=conn,
            event_type="slack:message",
            idempotency_key=idempotency_key,
            external_id=external_id,
            raw_payload=payload,
            trust_label="INTERNAL"
        )

        if result.is_duplicate:
            print(f"  [Stage 1] Event is duplicate (Idempotency Key: {idempotency_key}). Skipped.")
            return

        print(f"  [Stage 1 Ingested] SourceEvent ID: {result.source_event_id} (Deduplicated & Secret-Scrubbed)")

        # 2. Stage 2: Normalization (Reference extraction, anchor resolution, ledger link)
        processed_count = await process_unprocessed_source_events(session)
        print(f"  [Stage 2 Normalized] {processed_count} event(s) attached to canonical Change Graph!")
        print("  -> Run 'python scripts/inspect_tables.py' to view the updated Context Graph!")


def make_socket_mode_handler(loop: asyncio.AbstractEventLoop):
    def socket_mode_handler(client: SocketModeClient, req: SocketModeRequest):
        # 1. Immediately acknowledge receipt to Slack
        response = SocketModeResponse(envelope_id=req.envelope_id)
        client.send_socket_mode_response(response)

        # 2. Process events
        if req.type == "events_api":
            payload = req.payload
            event = payload.get("event", {})
            # Ignore messages sent by bots to avoid loops
            if event.get("bot_id") or event.get("subtype") == "bot_message":
                return

            # Schedule async processing on the main event loop
            asyncio.run_coroutine_threadsafe(handle_slack_event_async(payload), loop)

    return socket_mode_handler


async def run_listener():
    if not settings.SLACK_APP_TOKEN:
        print("[Error] SLACK_APP_TOKEN is not set in .env!")
        return

    print("=" * 80)
    print("  LAUNCHGRAPH REAL-TIME SLACK INGESTION LISTENER")
    print("=" * 80)
    print("Connecting to Slack via Socket Mode WebSocket ...")

    client = SocketModeClient(app_token=settings.SLACK_APP_TOKEN)
    loop = asyncio.get_running_loop()
    client.socket_mode_request_listeners.append(make_socket_mode_handler(loop))

    client.connect()
    print("[Connected] Socket Mode is ACTIVE! Listening for live Slack messages...")
    print("Tips:")
    print("  1. In your Slack app / workspace, invite the bot: '/invite @launchgraph_backend_m'")
    print("  2. Send any message in the channel (e.g., 'Deploying PROD-102 and closing PR #12')")
    print("  3. Watch LaunchGraph ingest, sanitize, resolve anchors, and link to the graph live!")
    print("Press Ctrl+C to exit.\n")

    try:
        while True:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nStopping Slack Listener...")
    finally:
        client.close()
        print("[Disconnected] Socket Mode closed.")


if __name__ == "__main__":
    try:
        asyncio.run(run_listener())
    except KeyboardInterrupt:
        pass
