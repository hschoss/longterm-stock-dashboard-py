"""Lesender Zugriff auf ops.job_runs/job_run_items fuer die Statusleiste und die
System-Seite. Schreiben passiert ausschliesslich in jobs/ (Batch-Protokoll)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from findash.storage.tables import JobRun


def get_last_successful_run(session: Session, job_type: str) -> JobRun | None:
    statement = (
        select(JobRun)
        .where(JobRun.job_type == job_type, JobRun.status.in_(["success", "partial_success"]))
        .order_by(JobRun.finished_at.desc())
        .limit(1)
    )
    return session.scalar(statement)
