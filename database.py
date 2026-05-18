import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

DB_URL = os.getenv("DB_URL")

# Si Django ya está configurado, usar sus settings de DB
try:
    import django
    from django.conf import settings as django_settings
    if django_settings.configured:
        db = django_settings.DATABASES['default']
        DB_URL = (
            f"postgresql+psycopg2://{db['USER']}:{db['PASSWORD']}"
            f"@{db['HOST']}:{db['PORT']}/{db['NAME']}"
        )
except Exception:
    pass

if not DB_URL:
    DB_URL = "postgresql+psycopg2://postgres:Jk9oe@localhost:5432/itscoming_db"

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()