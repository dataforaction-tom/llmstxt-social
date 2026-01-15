"""Celery app configuration."""

from celery import Celery
from celery.schedules import crontab

from llmstxt_api.config import settings

# Create Celery app
celery_app = Celery(
    "llmstxt_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "llmstxt_api.tasks.generate",
        "llmstxt_api.tasks.monitor",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max
    task_soft_time_limit=540,  # 9 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "check-due-subscriptions": {
        "task": "monitor.check_due_subscriptions",
        "schedule": crontab(hour=6, minute=0),  # Run daily at 6 AM UTC
    },
}
