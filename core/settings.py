from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-jmh_y^3u^-)mammy7=esvk5@v!z!&8m6g=%c!^b+idb=8ocat42')
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '').split(',') if os.getenv('DJANGO_ALLOWED_HOSTS') else []
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'predicciones',
]
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'core.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates','DIRS': [BASE_DIR / 'templates'],'APP_DIRS': True,'OPTIONS': {'context_processors': ['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages',],},},]
WSGI_APPLICATION = 'core.wsgi.application'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'itscoming_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'Jk9oe'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================
# CORS — Permitir peticiones del frontend React (Vite dev server)
# ==========================================
# En desarrollo, Vite puede usar 5173, 5174, 5175, etc. dependiendo del puerto libre.
# CORS_ALLOW_ALL_ORIGINS cubre todos los casos en DEBUG.
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Solo en desarrollo — en producción usar allowlist
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5174',
    'http://localhost:5175',
    'http://localhost:5176',
    'http://localhost:3000',
]
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = ['accept', 'authorization', 'content-type', 'x-csrftoken']
CORS_ALLOW_CREDENTIALS = False

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} | {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'scraper_errors.log'),
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'predicciones': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'predicciones.management.commands': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'predicciones.scheduler': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'predicciones.tasks': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'src.pipeline': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ==========================================
# CELERY + REDIS CONFIGURATION
# ==========================================
# Broker: Redis como cola de mensajes para las tareas asincronas.
# Result Backend: Redis para almacenar resultados de tareas.
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/1')

# --- APScheduler desactivado: usar Celery Beat ---
# APScheduler fue reemplazado por Celery Beat (configurado abajo).
# Ver predicciones/apps.py para el cambio.

# Serializar payloads como JSON (mas seguro que pickle para produccion)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Zona horaria consistente con Django
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Evitar que tareas se queden huerfanas si el worker muere
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Celery Beat Schedule: Tareas programadas automaticamente.
# Cada tarea se ejecuta en el horario especificado sin intervencion manual.
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Extraccion diaria de datos deportivos a las 06:00 AM
    'fetch-and-process-daily-data': {
        'task': 'predicciones.tasks.fetch_and_process_daily_data',
        'schedule': crontab(hour=6, minute=0),
        'options': {'queue': 'default'},
    },
}
