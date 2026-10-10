"""
Pytest configuration, fixtures, and database lifecycle management.
"""

import sys
from pathlib import Path
import pytest
import pytest_asyncio
import uuid
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport

# Add root directory to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from launchgraph_core.db.base import Base
from launchgraph_core.db.models import Workspace, Connection, AppUser
from services.ingester.main import app as ingester_app
from services.normalizer.main import app as normalizer_app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates fresh schema in SQLite memory, yields an isolated async session, and drops tables.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def test_workspace(db_session: AsyncSession) -> Workspace:
    """Creates a sample Workspace entity."""
    workspace = Workspace(
        id=uuid.uuid4(),
        slug="acme-corp",
        name="Acme Corporation",
        tier="pilot",
        settings={"data_retention_days": 30}
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture
async def test_connections(db_session: AsyncSession, test_workspace: Workspace):
    """Creates active connections for GitHub, Jira, and Slack."""
    gh_conn = Connection(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        source_type="GITHUB",
        status="ACTIVE",
        credentials=b"encrypted-token",
        config={"webhook_secret": "test-github-secret", "repo": "acme/backend"}
    )
    jira_conn = Connection(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        source_type="JIRA",
        status="ACTIVE",
        credentials=b"encrypted-oauth",
        config={"webhook_secret": "test-jira-secret", "domain": "acme.atlassian.net"}
    )
    slack_conn = Connection(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        source_type="SLACK",
        status="ACTIVE",
        credentials=b"encrypted-slack",
        config={"signing_secret": "test-slack-secret", "channel": "C01234PROD"}
    )
    db_session.add_all([gh_conn, jira_conn, slack_conn])
    await db_session.commit()
    return {"github": gh_conn, "jira": jira_conn, "slack": slack_conn}


@pytest_asyncio.fixture
async def ingester_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX test client for Ingester service overriding db session dependency."""
    from launchgraph_core.db.session import get_async_session

    async def override_get_session():
        yield db_session

    ingester_app.dependency_overrides[get_async_session] = override_get_session
    transport = ASGITransport(app=ingester_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    ingester_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def normalizer_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX test client for Normalizer service overriding db session dependency."""
    from launchgraph_core.db.session import get_async_session

    async def override_get_session():
        yield db_session

    normalizer_app.dependency_overrides[get_async_session] = override_get_session
    transport = ASGITransport(app=normalizer_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    normalizer_app.dependency_overrides.clear()
