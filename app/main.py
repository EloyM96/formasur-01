"""Application entry point for the prl-notifier FastAPI monolith."""
from fastapi import APIRouter, FastAPI

from .config import settings

app = FastAPI(title="prl-notifier", version="0.1.0")

router = APIRouter(tags=["health"])


@router.get("/health", summary="Infra healthcheck")
def healthcheck() -> dict[str, str]:
    """Simple health endpoint for infrastructure smoke tests."""

    return {"status": "ok", "environment": settings.environment}


app.include_router(router)
