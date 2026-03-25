from django.core.management.base import BaseCommand
import requests
from predicciones.models import Equipos

class Command(BaseCommand):
    help = 'Obtiene equipos de la Liga MX desde API-Football y los guarda en la base de datos'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando la conexión con API-Football...')

        # URL directa al endpoint de equipos
        url_api = "https://v3.football.api-sports.io/teams"
        
        # Parámetros: ID 262 es la Liga MX, y usamos la temporada 2023 o 2024
        parametros = {
            "league": "39", 
            "season": "2024" 
        }

        # ¡Pega tu API Key aquí dentro de las comillas!
        headers = {
            "x-apisports-key": "80b1e07d7f8906e33e9a6214288f3183"
        }

        try:
            # Hacemos la petición a la API
            respuesta = requests.get(url_api, headers=headers, params=parametros)
            respuesta.raise_for_status() 
            
            datos_json = respuesta.json()

            # Verificamos si la API nos devolvió errores (ej. llave inválida)
            if datos_json.get('errors'):
                self.stdout.write(self.style.ERROR(f"Error de la API: {datos_json['errors']}"))
                return

            # Extraemos la lista de equipos de la respuesta
            lista_equipos = datos_json.get('response', [])
            
            if not lista_equipos:
                self.stdout.write(self.style.WARNING("La API no devolvió equipos. Revisa la liga o temporada."))
                return

            # Recorremos cada equipo y lo guardamos
            for item in lista_equipos:
                # API-Football agrupa los datos del equipo dentro de la llave 'team'
                datos_equipo = item.get('team', {})
                nombre_equipo = datos_equipo.get('name')
                
                if nombre_equipo:
                    equipo, creado = Equipos.objects.update_or_create(
                        nombre=nombre_equipo,
                        defaults={
                            # Por ahora los inicializamos en 0. 
                            # Luego haremos otro script para traer las estadísticas precisas.
                            'prom_corners': 0.00, 
                            'prom_tiros_puerta': 0.00,
                            'prom_goles': 0.00
                        }
                    )
                    
                    if creado:
                        self.stdout.write(self.style.SUCCESS(f'✅ Equipo creado: {equipo.nombre}'))
                    else:
                        self.stdout.write(f'🔄 Equipo actualizado: {equipo.nombre}')

            self.stdout.write(self.style.SUCCESS('¡Proceso terminado con éxito! Tu base de datos tiene datos reales.'))

        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Error al conectar con la API: {e}'))