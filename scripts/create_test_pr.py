"""
Automated Test Pull Request Creator for LaunchGraph.
Creates a real test branch and Pull Request on GitHub (jashinspires/LaunchGraph)
and instantly syncs it through Stage 1 Ingestion and Stage 2 Normalization.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import base64
import time
import httpx
from launchgraph_core.config import settings
from scripts.github_sync import sync_github_events

REPO = settings.GITHUB_REPO or "jashinspires/LaunchGraph"
HEADERS = {
    "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "LaunchGraph-Test-PR-Creator"
}


async def create_test_pr():
    print("=" * 80)
    print("  CREATING REAL TEST PULL REQUEST ON GITHUB")
    print("=" * 80)
    print(f"Target Repository: {REPO}")

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Get base main branch SHA
        ref_res = await client.get(f"https://api.github.com/repos/{REPO}/git/ref/heads/main", headers=HEADERS)
        if ref_res.status_code != 200:
            print(f"[Error] Failed to get main branch SHA: {ref_res.status_code} {ref_res.text}")
            return
        base_sha = ref_res.json()["object"]["sha"]
        print(f"[1] Base main branch SHA: {base_sha[:8]}")

        # 2. Create unique test branch
        timestamp_slug = int(time.time())
        branch_name = f"test/prod-99-telemetry-{timestamp_slug}"
        create_ref_res = await client.post(
            f"https://api.github.com/repos/{REPO}/git/refs",
            headers=HEADERS,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha}
        )
        if create_ref_res.status_code != 201:
            print(f"[Error] Failed to create branch '{branch_name}': {create_ref_res.status_code} {create_ref_res.text}")
            return
        print(f"[2] Created branch: '{branch_name}'")

        # 3. Create a test file commit on that branch
        file_path = f"resources/test_event_{timestamp_slug}.txt"
        file_content = base64.b64encode(f"Telemetry sync test for PROD-99 at {timestamp_slug}".encode("utf-8")).decode("utf-8")
        put_file_res = await client.put(
            f"https://api.github.com/repos/{REPO}/contents/{file_path}",
            headers=HEADERS,
            json={
                "message": f"feat(telemetry): PROD-99 automated integration test {timestamp_slug}",
                "content": file_content,
                "branch": branch_name
            }
        )
        if put_file_res.status_code != 201:
            print(f"[Error] Failed to create test commit: {put_file_res.status_code} {put_file_res.text}")
            return
        print(f"[3] Created commit on branch '{branch_name}'")

        # 4. Open Pull Request
        pr_title = f"PROD-99: Real-time context graph sync verification #{timestamp_slug % 1000}"
        pr_body = (
            f"Automated test Pull Request for LaunchGraph.\n\n"
            f"- **Jira Anchor:** `PROD-99`\n"
            f"- **Target Branch:** `{branch_name}` -> `main`\n"
            f"- **Timestamp:** {timestamp_slug}\n"
        )
        create_pr_res = await client.post(
            f"https://api.github.com/repos/{REPO}/pulls",
            headers=HEADERS,
            json={
                "title": pr_title,
                "body": pr_body,
                "head": branch_name,
                "base": "main"
            }
        )
        if create_pr_res.status_code != 201:
            print(f"[Error] Failed to open pull request: {create_pr_res.status_code} {create_pr_res.text}")
            return

        pr_data = create_pr_res.json()
        pr_number = pr_data["number"]
        pr_url = pr_data["html_url"]
        print(f"\n[4] SUCCESS! Opened Real GitHub PR #{pr_number}:")
        print(f"    URL:   {pr_url}")
        print(f"    Title: '{pr_title}'")

        # 5. Automatically trigger LaunchGraph ingestion and normalization
        print("\n[5] Syncing new PR directly into LaunchGraph Context Graph ...")
        await sync_github_events(client)

    print("\n" + "=" * 80)
    print("Test PR created and synced! Run 'python scripts/inspect_tables.py' to view the tables.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(create_test_pr())
