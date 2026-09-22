from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "annual_report_analyzer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "filing-watch-daily": {
            "task": "app.workers.tasks.filing_watch_task",
            "schedule": settings.filing_watch_interval_hours * 3600,
        },
    },
)
