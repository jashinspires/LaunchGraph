"""
LaunchGraph Database Inspector.
Displays the current contents of webhook_inbox, source_events, change_events, and change_memberships.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
from sqlalchemy import select
from launchgraph_core.db.session import async_session_scope
from launchgraph_core.db.models import WebhookInbox, SourceEvent, ChangeEvent, ChangeMembership, Connection, LaunchCandidate, DecisionRun


async def inspect():
    async with async_session_scope() as session:
        print("\n" + "=" * 80)
        print("  LAUNCHGRAPH REAL-TIME CONTEXT GRAPH INSPECTOR")
        print("=" * 80)

        # 1. Connections
        conns = (await session.execute(select(Connection))).scalars().all()
        print(f"\n[1] CONNECTIONS ({len(conns)} active):")
        for c in conns:
            print(f"  - [{c.source_type}] ID: {c.id} | Status: {c.status}")

        # 2. Webhook Inbox (Deduplication Buffer)
        inbox = (await session.execute(select(WebhookInbox).order_by(WebhookInbox.received_at.desc()).limit(10))).scalars().all()
        print(f"\n[2] WEBHOOK INBOX (Last {len(inbox)} items):")
        if not inbox:
            print("  (Empty - no webhooks received yet)")
        for item in inbox:
            print(f"  - [{item.received_at.strftime('%H:%M:%S')}] Key: {item.idempotency_key} | Event: {item.event_type} | Status: {item.status}")

        # 3. Source Events (Sanitized & Scrubbed telemetry)
        events = (await session.execute(select(SourceEvent).order_by(SourceEvent.created_at.desc()).limit(10))).scalars().all()
        print(f"\n[3] SOURCE EVENTS ({len(events)} items, scrubbed & sanitized):")
        if not events:
            print("  (Empty - no source events yet)")
        for ev in events:
            processed_badge = "[PROCESSED]" if ev.is_processed else "[PENDING]"
            print(f"  - [{ev.created_at.strftime('%H:%M:%S')}] {processed_badge} | {ev.source_type} | ExtID: {ev.external_id}")
            if "--details" in sys.argv:
                print(f"      Payload: {ev.raw_payload}")

        # 4. Canonical Change Events (Context Graph Nodes)
        changes = (await session.execute(select(ChangeEvent).order_by(ChangeEvent.created_at.desc()).limit(10))).scalars().all()
        print(f"\n[4] CHANGE EVENTS ({len(changes)} canonical context graph nodes):")
        if not changes:
            print("  (Empty - run normalizer worker to assemble)")
        for ch in changes:
            print(f"  - [{ch.state.upper()}] Anchor: {ch.anchor_ref} | Title: '{ch.title}' (ID: {ch.id})")
            if "--details" in sys.argv and ch.description:
                print(f"      Description: {ch.description}")

        # 5. Change Memberships (Typed Ledger Edges L1-L8)
        memberships = (await session.execute(select(ChangeMembership).order_by(ChangeMembership.created_at.desc()).limit(10))).scalars().all()
        print(f"\n[5] CONTEXT GRAPH MEMBERSHIPS ({len(memberships)} ledger links):")
        if not memberships:
            print("  (Empty - no links formed yet)")
        for m in memberships:
            print(f"  - Link: {m.link_type} ({m.role}) | Ref: {m.ref_key} -> ChangeEvent: {m.change_event_id}")

        # 6. Launch Candidates (Stage 3 Tier Proposals)
        candidates = (await session.execute(select(LaunchCandidate).order_by(LaunchCandidate.created_at.desc()).limit(10))).scalars().all()
        print(f"\n[6] LAUNCH CANDIDATES (Stage 3 Proposals - {len(candidates)} candidates):")
        if not candidates:
            print("  (Empty - run decisioner worker or trigger /api/decisioner/process)")
        for cand in candidates:
            safe_badge = "[EXTERNAL SAFE]" if cand.is_external_safe else "[INTERNAL ONLY / REVIEW NEEDED]"
            print(f"  - [{cand.tier}] Score: {cand.score}/100 | Conf: {cand.confidence} | Status: {cand.status} | {safe_badge}")
            print(f"      Change ID: {cand.change_event_id}")
            if cand.reasons:
                print(f"      Reasons: {cand.reasons[0]}")
            if cand.safety_warnings:
                print(f"      Warnings: {'; '.join(cand.safety_warnings[:2])}")

        # 7. Decision Run Audits
        runs = (await session.execute(select(DecisionRun).order_by(DecisionRun.created_at.desc()).limit(5))).scalars().all()
        print(f"\n[7] DECISION RUN AUDITS ({len(runs)} immutable runs):")
        if not runs:
            print("  (Empty - no decision runs recorded)")
        for r in runs:
            print(f"  - Run ID: {r.id} | Model: {r.model_name} | k={r.k_samples} samples | Tokens: {r.evidence_pack_tokens} | Context Hash: {r.evidence_pack_hash[:12]}...")

        print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(inspect())
