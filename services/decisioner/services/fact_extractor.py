"""
Deterministic Fact Extractor for Stage 3 Decisioning.
Gathers objective, verifiable metrics directly from ChangeEvents, attached SourceEvents, and pull requests.
"""

import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from launchgraph_core.db.models.change_graph import ChangeEvent
from launchgraph_core.db.models.connection import SourceEvent


@dataclass
class ChangeFacts:
    changed_files_count: int = 0
    ci_test_status: str = "unknown"  # passed, failed, pending, unknown
    has_customer_docs: bool = False
    author_attribution: str = "unknown"
    is_breaking_change: bool = False
    is_infra_only: bool = False
    is_revert: bool = False
    availability: str = "unknown"  # internal, beta, ga, unknown
    ticket_priority: str = "medium"
    issue_type: str = "unknown"
    total_commits_count: int = 0
    raw_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DeterministicFactExtractor:
    """
    Extracts objective metrics from ChangeEvents and linked raw SourceEvents.
    No probabilistic LLM execution is performed here; all facts are deterministic.
    """

    DOCS_PATTERN = re.compile(
        r"(docs/|doc/|documentation/|\.md$|CHANGELOG|README|RELEASE_NOTES)",
        re.IGNORECASE
    )

    INFRA_ONLY_PATTERN = re.compile(
        r"^(\.github/|\.gitlab/|k8s/|deploy/|docker/|Dockerfile|docker-compose|\.env|\.circleci/)",
        re.IGNORECASE
    )

    CONVENTIONAL_INFRA_PREFIXES = ("chore:", "ci:", "build:", "test:", "tests:", "infra:")
    CONVENTIONAL_BREAKING_PREFIXES = ("breaking:", "feat!:", "fix!:", "refactor!:")

    @classmethod
    def extract_facts(
        cls,
        change_event: ChangeEvent,
        source_events: List[SourceEvent]
    ) -> ChangeFacts:
        facts = ChangeFacts()
        facts.availability = change_event.availability or "unknown"

        all_files_changed: set[str] = set()
        breaking_indicators: List[str] = []
        is_revert_detected = False
        authors: set[str] = set()
        ci_statuses: List[str] = []
        commit_count = 0
        jira_priority = "medium"
        jira_issue_type = "unknown"

        # Check ChangeEvent title/description first
        combined_text = f"{change_event.title or ''}\n{change_event.description or ''}"
        if cls._contains_breaking_change_text(combined_text):
            facts.is_breaking_change = True
            breaking_indicators.append("Title/Description contains breaking change pattern")

        if cls._contains_revert_text(change_event.title or ""):
            is_revert_detected = True

        for event in source_events:
            payload = event.raw_payload or {}
            source_type = event.source_type

            if source_type == "GITHUB":
                cls._extract_github_facts(
                    payload=payload,
                    all_files=all_files_changed,
                    authors=authors,
                    ci_statuses=ci_statuses,
                    breaking_indicators=breaking_indicators,
                    facts=facts
                )
                # Count commits
                if "commits" in payload:
                    commit_count += len(payload["commits"])
                elif "pull_request" in payload and "commits" in payload["pull_request"]:
                    commit_count += payload["pull_request"].get("commits", 0)

            elif source_type == "JIRA":
                issue = payload.get("issue", {})
                fields = issue.get("fields", {})
                if fields:
                    if "priority" in fields and isinstance(fields["priority"], dict):
                        jira_priority = fields["priority"].get("name", "medium").lower()
                    if "issuetype" in fields and isinstance(fields["issuetype"], dict):
                        jira_issue_type = fields["issuetype"].get("name", "unknown").lower()
                    if "assignee" in fields and isinstance(fields["assignee"], dict):
                        assignee_name = fields["assignee"].get("displayName") or fields["assignee"].get("name")
                        if assignee_name:
                            authors.add(assignee_name)

                    summary = fields.get("summary", "")
                    description = str(fields.get("description", ""))
                    if cls._contains_breaking_change_text(f"{summary}\n{description}"):
                        facts.is_breaking_change = True
                        breaking_indicators.append("Jira summary/description indicates breaking change")
                    if cls._contains_revert_text(summary):
                        is_revert_detected = True

            elif source_type == "SLACK":
                slack_ev = payload.get("event", {})
                user = slack_ev.get("user")
                if user:
                    authors.add(f"slack:{user}")

        facts.changed_files_count = len(all_files_changed)
        facts.total_commits_count = commit_count
        facts.ticket_priority = jira_priority
        facts.issue_type = jira_issue_type
        facts.is_revert = is_revert_detected

        # Check doc changes
        facts.has_customer_docs = any(cls.DOCS_PATTERN.search(f) for f in all_files_changed)

        # Check infra-only
        if all_files_changed and all(cls.INFRA_ONLY_PATTERN.search(f) for f in all_files_changed):
            facts.is_infra_only = True
        elif not all_files_changed and change_event.title.lower().startswith(cls.CONVENTIONAL_INFRA_PREFIXES):
            facts.is_infra_only = True

        # Check breaking changes
        if breaking_indicators:
            facts.is_breaking_change = True

        # CI Status
        if "failed" in ci_statuses:
            facts.ci_test_status = "failed"
        elif "passed" in ci_statuses or "success" in ci_statuses:
            facts.ci_test_status = "passed"
        elif "pending" in ci_statuses:
            facts.ci_test_status = "pending"
        else:
            facts.ci_test_status = "unknown"

        # Author attribution
        if authors:
            facts.author_attribution = ", ".join(sorted(authors))
        else:
            facts.author_attribution = "system"

        facts.raw_metrics = {
            "all_files_count": len(all_files_changed),
            "breaking_indicators": breaking_indicators,
            "authors_count": len(authors),
        }

        return facts

    @classmethod
    def _extract_github_facts(
        cls,
        payload: Dict[str, Any],
        all_files: set[str],
        authors: set[str],
        ci_statuses: List[str],
        breaking_indicators: List[str],
        facts: ChangeFacts
    ) -> None:
        pr = payload.get("pull_request")
        if pr:
            title = pr.get("title", "")
            body = pr.get("body", "") or ""
            user = pr.get("user", {}).get("login")
            if user:
                authors.add(user)

            if cls._contains_breaking_change_text(f"{title}\n{body}"):
                breaking_indicators.append("PR title or description contains breaking change")

            if cls._contains_revert_text(title):
                facts.is_revert = True

            # Changed files if listed in PR payload
            if "changed_files" in pr and isinstance(pr["changed_files"], list):
                for f in pr["changed_files"]:
                    all_files.add(f if isinstance(f, str) else f.get("filename", ""))

        # Commits
        commits = payload.get("commits", [])
        for c in commits:
            if not isinstance(c, dict):
                continue
            msg = c.get("message", "")
            author_val = c.get("author")
            author = None
            if isinstance(author_val, dict):
                author = author_val.get("name") or author_val.get("username") or author_val.get("login")
            elif isinstance(author_val, str):
                author = author_val
            if author:
                authors.add(author)

            if cls._contains_breaking_change_text(msg):
                breaking_indicators.append(f"Commit {c.get('id', '')[:7]} message contains breaking change")

            if cls._contains_revert_text(msg):
                facts.is_revert = True

            for f in c.get("added", []) + c.get("modified", []) + c.get("removed", []):
                all_files.add(f)

        # CI Checks / Check runs
        check_run = payload.get("check_run")
        if check_run:
            conclusion = check_run.get("conclusion")
            if conclusion:
                ci_statuses.append(conclusion.lower())

    @classmethod
    def _contains_breaking_change_text(cls, text: str) -> bool:
        lower = text.lower()
        if "breaking change" in lower or "breaking_change" in lower:
            return True
        if lower.startswith(cls.CONVENTIONAL_BREAKING_PREFIXES):
            return True
        if "deprecat" in lower or "removed endpoint" in lower or "backward-incompatible" in lower:
            return True
        return False

    @classmethod
    def _contains_revert_text(cls, text: str) -> bool:
        lower = text.lower().strip()
        return lower.startswith("revert") or "rollback" in lower or "reverted in #" in lower
