"""
LaunchGraph Stage 3 Decisioner Runner.
Executes Stage 3 evaluation across all ChangeEvents in launchgraph.db.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
from sqlalchemy import select
from launchgraph_core.db.session import async_session_scope
from launchgraph_core.db.models.change_graph import ChangeEvent
from services.decisioner.worker import evaluate_change_event


async def main():
    async with async_session_scope() as session:
        print("\n" + "=" * 80)
        print("  LAUNCHGRAPH STAGE 3: DECISION ENGINE PIPELINE RUNNER")
        print("=" * 80)

        changes = list((await session.execute(select(ChangeEvent))).scalars().all())
        print(f"\nFound {len(changes)} ChangeEvents in database to evaluate...\n")

        for change in changes:
            print(f"-> Evaluating ChangeEvent: '{change.title}' ({change.anchor_ref})")
            cand, run = await evaluate_change_event(session=session, change_event=change)
            print(f"   [RESULT] Tier: {cand.tier} | Score: {cand.score}/100 | Confidence: {cand.confidence}")
            print(f"   [EXTERNAL SAFE]: {cand.is_external_safe} | Status: {cand.status}")
            print(f"   [EVIDENCE PACK]: {run.evidence_pack_tokens} tokens | Hash: {run.evidence_pack_hash[:16]}...")
            if cand.reasons:
                print(f"   [PRIMARY REASON]: {cand.reasons[0]}")
            if cand.safety_warnings:
                print(f"   [SAFETY WARNINGS]: {'; '.join(cand.safety_warnings)}")
            print("-" * 80)

        await session.commit()
        print("\nAll ChangeEvents successfully evaluated and persisted with DecisionRun audits!")


if __name__ == "__main__":
    asyncio.run(main())

