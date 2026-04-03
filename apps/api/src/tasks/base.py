"""Base task class with progress reporting and DB session management."""

from datetime import datetime, timezone

from celery import Task
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings

settings = get_settings()

# Sync engine for Celery workers (Celery is sync, not async)
sync_engine = create_engine(settings.database_url_sync)
SyncSession = sessionmaker(sync_engine)


class PipelineTask(Task):
    """Base class for pipeline tasks with progress tracking."""

    _db: Session | None = None

    @property
    def db(self) -> Session:
        if self._db is None or not self._db.is_active:
            self._db = SyncSession()
        return self._db

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if self._db is not None:
            self._db.close()
            self._db = None

    def update_pipeline_run(self, run_id: str, **kwargs):
        """Update pipeline_run row with progress, stage, status, etc."""
        from ..models.pipeline_run import PipelineRun

        run = self.db.get(PipelineRun, run_id)
        if not run:
            return
        for key, value in kwargs.items():
            setattr(run, key, value)
        self.db.commit()

    def set_stage(self, run_id: str, stage: str, progress: float):
        self.update_pipeline_run(run_id, current_stage=stage, progress=progress)

    def complete_run(self, run_id: str):
        self.update_pipeline_run(
            run_id,
            status="completed",
            progress=1.0,
            completed_at=datetime.now(timezone.utc),
        )

    def fail_run(self, run_id: str, error: str):
        self.update_pipeline_run(
            run_id,
            status="failed",
            error_message=error,
            completed_at=datetime.now(timezone.utc),
        )
