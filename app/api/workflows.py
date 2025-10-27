"""Endpoints to trigger workflow dry-runs and executions."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.workflows.runner import WorkflowRunner


router = APIRouter(prefix="/workflows", tags=["workflows"])
workflow_runner = WorkflowRunner()


@router.post("/{playbook_name}/dry-run", summary="Ejecuta un playbook en modo dry-run")
def dry_run(playbook_name: str) -> dict:
    """Return the summary of running *playbook_name* without enqueuing jobs."""

    try:
        return workflow_runner.run(playbook_name, dry_run=True)
    except FileNotFoundError as exc:  # pragma: no cover - surfaced via HTTPException
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{playbook_name}/execute", summary="Ejecuta un playbook en modo real")
def execute(playbook_name: str) -> dict:
    """Run *playbook_name* enqueuing the resulting notification jobs."""

    try:
        return workflow_runner.run(playbook_name, dry_run=False)
    except FileNotFoundError as exc:  # pragma: no cover - surfaced via HTTPException
        raise HTTPException(status_code=404, detail=str(exc)) from exc


__all__ = ["router", "workflow_runner"]
