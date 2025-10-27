"""Application entry point for the prl-notifier FastAPI monolith."""
from fastapi import APIRouter, FastAPI

from .api.notifications import router as notifications_router
from .api.uploads import router as uploads_router
from .api.workflows import router as workflows_router
from .config import settings
from .logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
logger.info("app.startup", environment=settings.environment)

app = FastAPI(title="prl-notifier", version="0.1.0")

router = APIRouter(tags=["health"])


@router.get("/health", summary="Infra healthcheck")
def healthcheck() -> dict[str, str]:
    """Simple health endpoint for infrastructure smoke tests."""

    return {"status": "ok", "environment": settings.environment}


app.include_router(router)
app.include_router(notifications_router)
app.include_router(uploads_router)
app.include_router(workflows_router)
