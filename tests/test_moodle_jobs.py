from datetime import UTC, datetime
from pathlib import Path

from app.jobs.moodle_sync import (
    MoodleSyncJobDefinition,
    schedule_moodle_sync_jobs,
)
from app.models import CourseModel
from app.services.sync_courses import CourseSyncResult


class StubScheduler:
    def __init__(self) -> None:
        self.calls: dict[str, tuple] = {}

    def schedule_interval(self, job_id, func, minutes):
        self.calls[job_id] = (func, minutes)


class StubRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def run(self, playbook: str, dry_run: bool):
        self.calls.append((playbook, dry_run))


class StubService:
    def __init__(self, result: CourseSyncResult) -> None:
        self.result = result
        self.executions = 0

    def sync(self, *, source_path: Path):
        self.executions += 1
        return self.result

    @property
    def dry_run(self) -> bool:
        return self.result.dry_run


def test_schedule_jobs_registers_callbacks(tmp_path: Path):
    course = CourseModel(
        id=None,
        name="Prevención",
        hours_required=8,
        deadline_date=datetime.now(tz=UTC).date(),
        source="xlsx",
        source_reference="manual",
        attributes=None,
        created_at=datetime.now(tz=UTC),
    )
    result = CourseSyncResult(courses=[course], source="xlsx", dry_run=True)
    scheduler = StubScheduler()
    runner = StubRunner()
    service = StubService(result)
    job_definition = MoodleSyncJobDefinition(
        identifier="sync-moodle",
        playbook="sample_prl_playbook",
        source_path=tmp_path / "courses.xlsx",
        interval_minutes=60,
    )

    schedule_moodle_sync_jobs(scheduler, service, runner, [job_definition])

    assert "sync-moodle" in scheduler.calls

    callback, minutes = scheduler.calls["sync-moodle"]
    assert minutes == 60

    callback()

    assert service.executions == 1
    assert runner.calls == [("sample_prl_playbook", True)]
