# core/__init__.py
# Importar la instancia de Celery al arrancar Django para que el decorador
# @shared_task use esta app y para que Celery Beat pueda encontrar las tareas.
from .celery import app as celery_app

__all__ = ('celery_app',)
