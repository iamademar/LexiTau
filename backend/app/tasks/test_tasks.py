from app.core.celery import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def add(self, x: int, y: int) -> int:
    """
    Simple addition task for testing Celery connectivity
    
    Args:
        x: First number
        y: Second number
        
    Returns:
        Sum of x and y
    """
    try:
        result = x + y
        logger.info(f"Task {self.request.id}: Computing {x} + {y} = {result}")
        return result
    except Exception as exc:
        logger.error(f"Task {self.request.id} failed: {exc}")
        raise self.retry(exc=exc, countdown=60, max_retries=3)


@celery_app.task(bind=True)
def multiply(self, x: int, y: int) -> int:
    """
    Simple multiplication task for testing Celery connectivity
    
    Args:
        x: First number
        y: Second number
        
    Returns:
        Product of x and y
    """
    try:
        result = x * y
        logger.info(f"Task {self.request.id}: Computing {x} * {y} = {result}")
        return result
    except Exception as exc:
        logger.error(f"Task {self.request.id} failed: {exc}")
        raise self.retry(exc=exc, countdown=60, max_retries=3)