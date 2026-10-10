"""
B0.3 Connector Contracts & Ingress Schemas
Frozen schemas for incoming payloads from GitHub, Jira, and Slack.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# GitHub Webhook Schemas
# ============================================================================

class GitHubUser(BaseModel):
    login: str
    id: int
    avatar_url: Optional[str] = None


class GitHubRepo(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool = False
    html_url: str


class GitHubPullRequest(BaseModel):
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    merged: bool = False
    merged_at: Optional[datetime] = None
    head_ref: Optional[str] = Field(default=None, alias="head.ref")
    base_ref: Optional[str] = Field(default=None, alias="base.ref")
    user: GitHubUser
    html_url: str


class GitHubCommit(BaseModel):
    id: str
    message: str
    timestamp: Optional[datetime] = None
    author: Dict[str, Any]
    url: Optional[str] = None


class GitHubRelease(BaseModel):
    id: int
    tag_name: str
    name: Optional[str] = None
    body: Optional[str] = None
    draft: bool = False
    prerelease: bool = False
    published_at: Optional[datetime] = None
    html_url: str


class GitHubWebhookPayload(BaseModel):
    action: Optional[str] = None
    number: Optional[int] = None
    pull_request: Optional[GitHubPullRequest] = None
    commits: Optional[List[GitHubCommit]] = None
    release: Optional[GitHubRelease] = None
    repository: GitHubRepo
    sender: GitHubUser


# ============================================================================
# Jira Webhook Schemas
# ============================================================================

class JiraIssueFields(BaseModel):
    summary: str
    description: Optional[Any] = None  # Text or Atlassian Document Format JSON
    issuetype: Dict[str, Any]
    status: Dict[str, Any]
    priority: Optional[Dict[str, Any]] = None
    creator: Optional[Dict[str, Any]] = None
    assignee: Optional[Dict[str, Any]] = None
    updated: Optional[str] = None
    fixVersions: Optional[List[Dict[str, Any]]] = None
    labels: Optional[List[str]] = None


class JiraIssue(BaseModel):
    id: str
    key: str
    self: str
    fields: JiraIssueFields


class JiraWebhookPayload(BaseModel):
    webhookEvent: str
    issue_event_type_name: Optional[str] = None
    timestamp: int
    issue: Optional[JiraIssue] = None
    version: Optional[Dict[str, Any]] = None


# ============================================================================
# Slack Webhook & Events API Schemas
# ============================================================================

class SlackUrlVerification(BaseModel):
    token: Optional[str] = None
    challenge: str
    type: str = "url_verification"


class SlackEventItem(BaseModel):
    type: str
    channel: str
    user: Optional[str] = None
    text: Optional[str] = None
    ts: str
    thread_ts: Optional[str] = None
    subtype: Optional[str] = None


class SlackEventCallback(BaseModel):
    token: Optional[str] = None
    team_id: str
    api_app_id: Optional[str] = None
    event: SlackEventItem
    type: str = "event_callback"
    event_id: str
    event_time: int
