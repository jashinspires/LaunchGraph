"""
Change Lifecycle and Availability Tracker.
Computes lifecycle transitions: discovered -> in_progress -> merged -> closed
and tracks product availability: unknown, internal, beta, ga.
"""

from typing import Dict, Any


class LifecycleTracker:
    """
    Computes change state and availability based on attached source events.
    """

    @classmethod
    def evaluate_state(
        cls,
        current_state: str,
        source_type: str,
        event_payload: Dict[str, Any]
    ) -> str:
        """
        Calculates new lifecycle state given incoming telemetry.
        """
        # If already closed/reverted, preserve closed state unless reopened
        if current_state == "closed":
            if event_payload.get("action") == "reopened":
                return "in_progress"
            return "closed"

        # GitHub PR states
        if source_type == "GITHUB":
            pr = event_payload.get("pull_request")
            if pr:
                if pr.get("merged") is True or event_payload.get("action") == "closed" and pr.get("merged_at"):
                    return "merged"
                if event_payload.get("action") == "closed":
                    return "closed"
                if pr.get("state") == "open":
                    return "in_progress"

        # Jira Issue status categories
        if source_type == "JIRA":
            fields = event_payload.get("issue", {}).get("fields", {})
            status_category = fields.get("status", {}).get("statusCategory", {}).get("key")
            if status_category == "done":
                return "merged"
            elif status_category == "indeterminate":
                return "in_progress"

        return current_state or "discovered"

    @classmethod
    def evaluate_availability(
        cls,
        current_availability: str,
        labels: list[str],
        release_published: bool = False
    ) -> str:
        """
        Infers availability from release publications and labels.
        """
        if release_published:
            return "ga"

        label_set = {l.lower() for l in labels} if labels else set()

        if "ga" in label_set or "general-availability" in label_set:
            return "ga"
        if "beta" in label_set or "public-beta" in label_set:
            return "beta"
        if "internal" in label_set or "dogfood" in label_set:
            return "internal"

        return current_availability or "unknown"
