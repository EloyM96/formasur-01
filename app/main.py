"""Application entry point for the prl-notifier FastAPI monolith."""
from fastapi import FastAPI

from .config import settings

app = FastAPI(title="prl-notifier", version="0.1.0")


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    """Simple health endpoint for infrastructure smoke tests."""
    return {"status": "ok", "environment": settings.environment}
