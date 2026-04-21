from celery import Celery

from kartochka.config import settings

celery_app = Celery(
    "kartochka",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-expired-subscriptions": {
            "task": "kartochka.workers.tasks.check_expired_subscriptions",
            "schedule": 3600.0,
        },
    },
)
