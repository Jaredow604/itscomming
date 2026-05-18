"""
celery.py -- Punto de entrada de Celery para el proyecto 'It's Coming'.

Este módulo configura la instancia de Celery a nivel de proyecto Django.
Se importa automáticamente al arrancar Django gracias al __init__.py de core/.

Ejecución del worker:
    celery -A core worker --loglevel=info --pool=solo   (Windows)
    celery -A core worker --loglevel=info               (Linux/Mac)

Ejecución de Celery Beat (scheduler):
    celery -A core beat --loglevel=info
"""

import os

from celery import Celery

# Establecer el módulo de settings de Django para Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Crear instancia de Celery vinculada al proyecto Django
app = Celery('itscoming')

# Leer configuración desde settings.py bajo el namespace CELERY_
# Esto permite que todas las variables CELERY_* en settings.py sean
# reconocidas automáticamente (ej. CELERY_BROKER_URL -> broker_url).
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover: Celery escanea todos los archivos tasks.py dentro
# de cada app registrada en INSTALLED_APPS.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tarea de diagnóstico para verificar que Celery funciona correctamente."""
    print(f'Request: {self.request!r}')
