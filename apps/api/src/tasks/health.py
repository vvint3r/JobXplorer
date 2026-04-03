"""Health check task for verifying Celery worker connectivity."""

from ..celery_app import celery_app


@celery_app.task(name="health.ping")
def ping():
    """Simple health check — returns 'pong' if the worker is alive."""
    return "pong"
