from django.test import TestCase
from django.conf import settings


class DatabaseConfigTest(TestCase):
    def test_database_is_postgresql(self):
        engine = settings.DATABASES['default']['ENGINE']
        self.assertEqual(engine, 'django.db.backends.postgresql')

    def test_database_name_set(self):
        name = settings.DATABASES['default']['NAME']
        self.assertTrue(len(name) > 0)


class ModuleImportTest(TestCase):
    def test_entity_resolver_imports(self):
        from predicciones.entity_resolver import clean_team_name
        self.assertTrue(callable(clean_team_name))

    def test_models_imports(self):
        from predicciones.models import Equipos, Partido, DailySchedule
        self.assertIsNotNone(Equipos)
        self.assertIsNotNone(Partido)
        self.assertIsNotNone(DailySchedule)
