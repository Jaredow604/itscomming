import os
import django
import pandas as pd

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from predicciones.models import Equipos, Partido
from django.db.models import Avg, Q

def actualizar_promedios():
    print("📊 Calculando promedios históricos para todos los equipos...")
    equipos = Equipos.objects.all()
    
    for eq in equipos:
        # Buscamos todos sus partidos jugados (local o visita)
        partidos = Partido.objects.filter(Q(local=eq) | Q(visitante=eq), jugado=True)
        count = partidos.count()
        
        if count > 0:
            total_goles = 0
            for p in partidos:
                if p.local == eq: total_goles += p.goles_local
                else: total_goles += p.goles_visitante
            
            eq.prom_goles = total_goles / count
            # Ponemos promedios base de tiros y corners para que Poisson no falle
            eq.prom_tiros_puerta = 4.5 
            eq.prom_corners = 5.2
            eq.save()
            print(f"✅ {eq.nombre}: {round(eq.prom_goles, 2)} goles/partido")

if __name__ == '__main__':
    actualizar_promedios()