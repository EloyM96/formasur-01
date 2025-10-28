"""Jobs that orchestrate Moodle synchronisation and workflow execution."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.logging import get_logger
from app.services.sync_courses import CourseSyncResult, CourseSyncService
from app.workflows.runner import WorkflowRunner

from .scheduler import Scheduler


@dataclass(slots=True)
class MoodleSyncJobDefinition:
    """Declarative description of a Moodle synchronisation job."""

    identifier: str
    playbook: str
    source_path: Path
    interval_minutes: int


def schedule_moodle_sync_jobs(
    scheduler: Scheduler,
    service: CourseSyncService,
    runner: WorkflowRunner,
    jobs: Iterable[MoodleSyncJobDefinition],
) -> None:
    """Register Moodle synchronisation jobs respecting the service dry-run mode."""

    logger = get_logger(__name__)

    for job in jobs:
        def _run_job(definition: MoodleSyncJobDefinition = job) -> None:
            result = _execute_sync(service, definition)
            logger.info(
                "moodle.sync.completed",
                job=definition.identifier,
                courses=len(result.courses),
                source=result.source,
                dry_run=result.dry_run,
            )
            runner.run(definition.playbook, dry_run=result.dry_run)

        scheduler.schedule_interval(job.identifier, _run_job, job.interval_minutes)


def _execute_sync(
    service: CourseSyncService, definition: MoodleSyncJobDefinition
) -> CourseSyncResult:
    return service.sync(source_path=definition.source_path)


__all__ = [
    "MoodleSyncJobDefinition",
    "schedule_moodle_sync_jobs",
]
