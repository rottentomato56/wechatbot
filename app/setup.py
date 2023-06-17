import settings
from celery import Celery
from flask_caching import Cache

cache = Cache(config={'CACHE_TYPE': 'redis', 'CACHE_REDIS_URL': settings.REDIS_URL})

celery = Celery(broker=settings.CELERY_BROKER_URL)
celery.config_from_object('settings')

