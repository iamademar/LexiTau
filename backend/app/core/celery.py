from celery import Celery
from app.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "lexitau",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.document_tasks", "app.tasks.test_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

# Use default queue for all tasks to simplify initial setup
# Can be customized later for production
# celery_app.conf.task_routes = {
#     "app.tasks.document_tasks.*": {"queue": "documents"},
#     "app.tasks.test_tasks.*": {"queue": "test"},
# }