"""Celery configuration for background task processing."""
import os

from celery import Celery

# Celery configuration
celery_app = Celery(
    "dspy_agent",
    broker=os.getenv("CELERY_BROKER_URL", "pyamqp://guest:guest@localhost:5672//"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=[
        "tasks.document_tasks",
        "tasks.bulk_index_tasks"
    ]
)

# Celery configuration settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,  # Results expire after 1 hour
    task_routes={
        "tasks.document_tasks.*": {"queue": "document_processing"},
        "tasks.bulk_index_tasks.*": {"queue": "bulk_indexing"},
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression="gzip",
    result_compression="gzip",
)

# Optional: Configure periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-expired-results": {
        "task": "tasks.maintenance_tasks.cleanup_expired_results",
        "schedule": 3600.0,  # Run every hour
    },
}

if __name__ == "__main__":
    celery_app.start()
