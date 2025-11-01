"""File upload endpoints for ingesting Moodle PRL spreadsheets."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from ..db import get_session
from ..logging import get_logger
from ..models import UploadedFile
from ..modules.ingest import course_loader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_DIR = PROJECT_ROOT / "uploads"
ALLOWED_EXTENSIONS = {".xlsx"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MiB


router = APIRouter(prefix="/uploads", tags=["uploads"])


logger = get_logger(__name__)


def _validate_extension(filename: str | None) -> str:
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre del archivo es obligatorio.",
        )

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extensión de archivo no soportada. Solo se permiten ficheros XLSX.",
        )

    return extension


@router.post("", summary="Subir fichero XLSX con matrículas Moodle")
async def upload_file(
    file: UploadFile,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """Validate, persist and parse a Moodle PRL spreadsheet upload."""

    logger.info(
        "uploads.xlsx.received",
        filename=file.filename,
        content_type=file.content_type,
    )

    try:
        extension = _validate_extension(file.filename)
    except HTTPException:
        logger.warning(
            "uploads.xlsx.rejected",
            filename=file.filename,
            reason="invalid_extension",
        )
        raise

    contents = await file.read()
    file_size = len(contents)
    logger.info(
        "uploads.xlsx.buffered",
        filename=file.filename,
        size=file_size,
    )
    if file_size == 0:
        logger.warning(
            "uploads.xlsx.rejected",
            filename=file.filename,
            reason="empty_file",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fichero está vacío.",
        )
    if file_size > MAX_FILE_SIZE:
        logger.warning(
            "uploads.xlsx.rejected",
            filename=file.filename,
            reason="file_too_large",
            size=file_size,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fichero supera el tamaño máximo permitido de 5MB.",
        )

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    stored_path = UPLOADS_DIR / stored_name
    stored_path.write_bytes(contents)
    await file.close()

    logger.info(
        "uploads.xlsx.saved",
        filename=file.filename,
        stored_path=str(stored_path),
        size=file_size,
    )

    relative_path = PurePosixPath("uploads") / stored_name
    upload = UploadedFile(
        original_name=file.filename,
        stored_path=relative_path.as_posix(),
        mime=file.content_type or "application/octet-stream",
        size=file_size,
    )

    db.add(upload)
    db.commit()
    db.refresh(upload)

    try:
        result = course_loader.ingest_workbook(
            stored_path, db=db, workbook_label=file.filename
        )
    except Exception as exc:
        logger.exception(
            "uploads.xlsx.ingest_failed",
            filename=file.filename,
            stored_path=str(stored_path),
            error=str(exc),
        )
        raise

    summary = result.summary
    logger.info(
        "uploads.xlsx.ingest_completed",
        filename=file.filename,
        stored_path=str(stored_path),
        total_rows=summary.total_rows,
        missing_columns=summary.missing_columns,
        errors=summary.errors,
        stats=asdict(result.stats),
    )

    return {
        "file": {
            "id": upload.id,
            "original_name": upload.original_name,
            "stored_path": upload.stored_path,
            "mime": upload.mime,
            "size": upload.size,
        },
        "summary": jsonable_encoder(asdict(result.summary)),
        "ingest": jsonable_encoder(asdict(result.stats)),
    }
