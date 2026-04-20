"""Celery entry point for bakery v2."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("bakery_v2")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
