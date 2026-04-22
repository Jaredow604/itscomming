from django.core.management.base import BaseCommand
import requests
from django.utils.dateparse import parse_datetime
from predicciones.models import Equipos, Partido

class Command(BaseCommand):
    help = 'Descarga el calendario de la Premier League con búsqueda inteligente de equipos'

    def handle(self, *args, **kwargs):
        self.stdout.write('Descargando el calendario de partidos (football-data.org)...')

        url_api = "https://api.football-data.org/v4/competitions/PL/matches"
        
        # Pega aquí tu token de football-data.org
        headers = {
            "X-Auth-Token": "3b78612c4bab4114abe352da00b7558d" 
        }

        try:
            respuesta = requests.get(url_api, headers=headers)
            if respuesta.status_code != 200:
                self.stdout.write(self.style.ERROR(f"Error de la API: {respuesta.text}"))
                return
                
            datos_json = respuesta.json()
            lista_partidos = datos_json.get('matches', [])
            
            if not lista_partidos:
                self.stdout.write(self.style.WARNING("No se encontraron partidos."))
                return

            # --- EL ALGORITMO INTELIGENTE ---
            # Traemos todos los equipos de la base de datos a la memoria de Python
            equipos_db = list(Equipos.objects.all())

            def encontrar_equipo(nombre_api):
                nombre_api_clean = nombre_api.lower().strip()
                
                # 0. Excepciones extremas (Apodos vs Nombres Oficiales)
                excepciones = {
                    "wolverhampton wanderers fc": "wolves",
                    "nottingham forest fc": "nott'm forest",
                    "manchester united fc": "man united",
                    "manchester city fc": "man city"
                }
                
                # Si el nombre de la API está en las excepciones, lo traducimos al apodo
                if nombre_api_clean in excepciones:
                    nombre_api_clean = excepciones[nombre_api_clean]

                # 1. Búsqueda exacta
                for eq in equipos_db:
                    if eq.nombre.lower().strip() == nombre_api_clean:
                        return eq
                        
                # 2. Búsqueda parcial
                for eq in equipos_db:
                    if eq.nombre.lower().strip() in nombre_api_clean:
                        return eq
                        
                return None
            # --------------------------------

            partidos_creados = 0
            partidos_actualizados = 0
            errores = set() # Usamos un set para no repetir el mismo error 40 veces

            for item in lista_partidos:
                nombre_local_api = item['homeTeam']['name']
                nombre_visita_api = item['awayTeam']['name']

                # Usamos nuestra nueva función para encontrarlos
                equipo_local = encontrar_equipo(nombre_local_api)
                equipo_visita = encontrar_equipo(nombre_visita_api)

                if not equipo_local:
                    errores.add(f"De plano no existe en la BD: {nombre_local_api}")
                    continue
                if not equipo_visita:
                    errores.add(f"De plano no existe en la BD: {nombre_visita_api}")
                    continue

                # Guardar partido
                fecha_partido = parse_datetime(item['utcDate'])
                estado = item['status'] 

                partido, creado = Partido.objects.get_or_create(
                    local=equipo_local,
                    visitante=equipo_visita,
                    fecha=fecha_partido,
                    defaults={'fstatus': estado}
                )
                
                if not creado and partido.fstatus != estado:
                    partido.fstatus = estado
                    partido.save()
                    partidos_actualizados += 1
                elif creado:
                    partidos_creados += 1

            # Imprimir resumen de éxito
            self.stdout.write(self.style.SUCCESS(f'\n¡Éxito! {partidos_creados} creados, {partidos_actualizados} actualizados.'))
            
            # Si a pesar de todo faltan equipos, te lo dirá claramente
            if errores:
                self.stdout.write(self.style.WARNING("\nEquipos que faltan en tu tabla 'Equipos':"))
                for error in errores:
                    self.stdout.write(self.style.WARNING(f"- {error}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error crítico: {e}'))