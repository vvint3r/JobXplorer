"""Celery tasks."""

from . import health  # noqa: F401 — ensure task registration
from . import pipeline_chain  # noqa: F401
from . import resume_parse  # noqa: F401
