"""
Unit tests for Reference Extractor.
"""

from services.normalizer.services.extractor import ReferenceExtractor


def test_extract_jira_keys():
    text = "PROJ-1024: Fix rate limit bypass in PROJ-999 and CORE-12."
    refs = ReferenceExtractor.extract_from_text(text)
    assert refs.jira_keys == ["CORE-12", "PROJ-1024", "PROJ-999"]


def test_extract_pr_numbers():
    text = "Fixes #142 and closes https://github.com/acme/repo/pull/580."
    refs = ReferenceExtractor.extract_from_text(text)
    assert refs.pr_numbers == [142, 580]


def test_extract_commit_shas():
    text = "Cherry-picked from 9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e."
    refs = ReferenceExtractor.extract_from_text(text)
    assert "9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e" in refs.commit_shas


def test_combined_extraction():
    text = "PROJ-200: Add SSO integration (#45). Merged commit 1a2b3c4d5e6f7a8b9c0d."
    refs = ReferenceExtractor.extract_from_text(text)
    assert refs.jira_keys == ["PROJ-200"]
    assert refs.pr_numbers == [45]
    assert refs.commit_shas == ["1a2b3c4d5e6f7a8b9c0d"]
