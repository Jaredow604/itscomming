import requests
import pandas as pd
import numpy as np
from scipy.stats import poisson
from google import genai
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from .models import Equipos, Partido
import json

# CONFIGURACIÓN
ODDS_API_KEY = "dee3f700e79c237daf0a98fb20d77822"
client = genai.Client(api_key="AIzaSyDGkcCI5UQkbIRPvIUi5HCewLN5mKmrzWg")

def home(request):
    return render(request, 'index.html')

def modelo_elite_ensemble(local, visita):
    # 1. Obtener promedios de la liga
    all_teams = Equipos.objects.all().values()
    df_l = pd.DataFrame(list(all_teams))
    avg_g = float(df_l['prom_goles'].mean()) if not df_l.empty and df_l['prom_goles'].mean() > 0 else 1.3
    
    # 2. Calcular Lambdas (Expectativa de goles)
    l_l = (float(local.prom_goles) / avg_g) * avg_g * 1.10 # Ventaja local
    l_v = (float(visita.prom_goles) / avg_g) * avg_g
    
    # 3. Matriz de Probabilidades (Bucle Seguro)
    prob_local, prob_visita, prob_empate = 0, 0, 0
    for i in range(9): # Goles Local
        for j in range(9): # Goles Visita
            p = poisson.pmf(i, l_l) * poisson.pmf(j, l_v)
            if i > j: prob_local += p
            elif j > i: prob_visita += p
            else: prob_empate += p
            
    return round(prob_local*100, 1), round(prob_empate*100, 1), round(prob_visita*100, 1)

@csrf_exempt
def chatbot_web(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            msg = data.get("message", "").lower()
            
            # Inicializamos variables para evitar el "not defined"
            res_l, res_e, res_v = 0, 0, 0
            ctx = "No encontré datos históricos suficientes para un análisis profundo."
            equipo_encontrado = None

            # Búsqueda de equipo
            for eq in Equipos.objects.all():
                if eq.nombre.lower() in msg:
                    equipo_encontrado = eq
                    break
            
            if equipo_encontrado:
                p = Partido.objects.filter(Q(local=equipo_encontrado) | Q(visitante=equipo_encontrado)).order_by('-fecha').first()
                if p:
                    res_l, res_e, res_v = modelo_elite_ensemble(p.local, p.visitante)
                    ctx = f"SISTEMA: {p.local.nombre} ({res_l}%) vs {p.visitante.nombre} ({res_v}%). Empate: {res_e}%."

            response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=f"Eres el analista de It's Coming. Contexto: {ctx}. Pregunta: {msg}. Da un pick basado en la probabilidad."
            )
            
            return JsonResponse({
                "reply": response.text, 
                "prob": res_l, # Ya no fallará porque se inicializó en 0
                "confidence": "ALTA" if res_l > 50 else "MEDIA"
            })
        except Exception as e:
            return JsonResponse({"reply": f"Error técnico de sistema: {str(e)}"}, status=500)
    return render(request, 'index.html')

def chatbot_prediccion(request, nombre_equipo=None, partido_id=None):
    return JsonResponse({"status": "active"})