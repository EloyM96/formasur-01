"""Background queue client helpers."""
from dataclasses import dataclass

from .config import settings


@dataclass
class QueueClient:
    """Minimal queue client placeholder for background jobs."""

    url: str

    def enqueue(self, task_name: str, payload: dict) -> None:
        """Stub enqueue implementation to be replaced with a real broker."""
        raise NotImplementedError(f"Queue backend not yet implemented: {task_name} -> {payload}")


queue_client = QueueClient(url=settings.queue_url)
