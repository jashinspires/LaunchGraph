"""
LaunchGraph Stage 1: Ingestion Microservice (:8001)
Receives inbound telemetry from GitHub, Jira, and Slack with deduplication and secret scrubbing.
"""

from fastapi import FastAPI
from services.ingester.config import ingester_settings
from services.ingester.routes.github import router as github_router
from services.ingester.routes.jira import router as jira_router
from services.ingester.routes.slack import router as slack_router

app = FastAPI(
    title="LaunchGraph Ingestion Service",
    description="Live webhook ingress and security sanitization for GitHub, Jira, and Slack",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Mount Webhook Routes
app.include_router(github_router)
app.include_router(jira_router)
app.include_router(slack_router)


@app.get("/health", tags=["System"])
async def health_check():
    """Service liveness probe."""
    return {"status": "healthy", "service": "ingester", "port": ingester_settings.PORT}


@app.get("/metrics", tags=["System"])
async def metrics():
    """Basic service health metrics."""
    return {
        "status": "operational",
        "service": ingester_settings.SERVICE_NAME,
        "supported_sources": ["GITHUB", "JIRA", "SLACK"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=ingester_settings.HOST, port=ingester_settings.PORT)
