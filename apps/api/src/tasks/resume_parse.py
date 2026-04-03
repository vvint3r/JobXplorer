"""Celery task for async resume PDF parsing."""

import logging

from ..celery_app import celery_app
from .base import PipelineTask

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, base=PipelineTask, name="resume.parse")
def parse_resume_task(self, resume_id: str, user_id: str):
    """Download resume PDF from storage, parse it, and update the DB row.

    Triggered after a resume upload.
    """
    from ..models.resume import Resume
    from ..services.storage import TenantStorage
    from ..core.auto_application.resume_parser import parse_resume_from_bytes

    try:
        resume = self.db.get(Resume, resume_id)
        if not resume:
            logger.error(f"Resume {resume_id} not found")
            return {"status": "error", "message": "Resume not found"}

        if not resume.pdf_storage_path:
            logger.error(f"Resume {resume_id} has no PDF path")
            return {"status": "error", "message": "No PDF path"}

        # Download PDF from Supabase Storage
        import asyncio
        storage = TenantStorage(resume.user_id)

        # Run async download in sync context
        loop = asyncio.new_event_loop()
        try:
            pdf_bytes = loop.run_until_complete(storage.download_resume(resume.pdf_storage_path))
        finally:
            loop.close()

        # Parse PDF
        components, raw_text = parse_resume_from_bytes(pdf_bytes)

        # Update resume record
        resume.components_json = components.to_dict()
        resume.resume_text = raw_text
        self.db.commit()

        logger.info(f"Successfully parsed resume {resume_id}: {len(raw_text)} chars, {len(components.skills)} skills")
        return {
            "status": "ok",
            "text_length": len(raw_text),
            "skills_count": len(components.skills),
            "experience_count": len(components.work_experience),
        }

    except ImportError as e:
        logger.error(f"PDF parsing dependency missing: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.exception(f"Failed to parse resume {resume_id}")
        return {"status": "error", "message": str(e)}
