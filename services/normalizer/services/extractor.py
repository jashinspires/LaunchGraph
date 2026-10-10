"""
Deterministic Reference Extractor.
Extracts Jira issue keys, GitHub PR numbers, and Git commit SHAs using compiled regex patterns.
"""

import re
from typing import Set, List
from pydantic import BaseModel, Field

# Compiled regex patterns per LLD specifications
JIRA_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-[0-9]+)\b")
GITHUB_PR_SHORT_PATTERN = re.compile(r"(?:^|[\s(,])#([0-9]+)\b")
GITHUB_PR_URL_PATTERN = re.compile(r"https?://github\.com/[^/\s]+/[^/\s]+/pull/([0-9]+)")
COMMIT_SHA_PATTERN = re.compile(r"\b([a-f0-9]{7,40})\b")


class ExtractedReferences(BaseModel):
    jira_keys: List[str] = Field(default_factory=list)
    pr_numbers: List[int] = Field(default_factory=list)
    commit_shas: List[str] = Field(default_factory=list)


class ReferenceExtractor:
    """
    High-precision deterministic extractor scanning titles, commit messages, and PR bodies.
    """

    @classmethod
    def extract_from_text(cls, text: str) -> ExtractedReferences:
        if not text or not isinstance(text, str):
            return ExtractedReferences()

        # Jira keys
        jira_keys: Set[str] = set(JIRA_KEY_PATTERN.findall(text))

        # PR numbers
        pr_numbers: Set[int] = set()
        for num_str in GITHUB_PR_SHORT_PATTERN.findall(text):
            try:
                pr_numbers.add(int(num_str))
            except ValueError:
                pass
        for num_str in GITHUB_PR_URL_PATTERN.findall(text):
            try:
                pr_numbers.add(int(num_str))
            except ValueError:
                pass

        # Commit SHAs (filter out pure number sequences)
        commit_shas: Set[str] = set()
        for sha in COMMIT_SHA_PATTERN.findall(text):
            # Exclude strings that are solely decimal digits to avoid misidentifying large numbers
            if not sha.isdigit():
                commit_shas.add(sha)

        return ExtractedReferences(
            jira_keys=sorted(list(jira_keys)),
            pr_numbers=sorted(list(pr_numbers)),
            commit_shas=sorted(list(commit_shas))
        )
