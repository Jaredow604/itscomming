import os
import json
import torch
import torch.nn as nn
import requests
import pandas as pd
import numpy as np
import joblib
from sqlalchemy import create_engine
from google import genai
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv

load_dotenv()

from .models import Equipos, Partido

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.models.networks.player_prop_net import PlayerPropNet 
from src.models.datasets.fbref_player_dataset import FBrefPlayerDataset
from src.models.networks.match_prediction_net import MatchPredictionNet

# 1. CONFIGURACIÓN (Seguridad vía variables de entorno)
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None
    print("[WARNING] No se encontro GEMINI_API_KEY en el entorno. Chatbot IA funcionara limitado.")

# 2. SE ELIMINÓ LA CLASE LOCAL FootballOracleNet, AHORA IMPORTAMOS MatchPredictionNet DESDE LA ARQUITECTURA GENERAL

# 3. CARGAR EL "CEREBRO" GLOBALMENTE
try:
    MODELO_IA = MatchPredictionNet(input_dim=12) # actualizado a v2
    if os.path.exists('oracle_h2h_brain.pth'):
        try:
            MODELO_IA.load_state_dict(torch.load('oracle_h2h_brain.pth', map_location='cpu', weights_only=True))
            MODELO_IA.eval() 
            print("[OK] Cerebro H2H PyTorch (MatchPredictionNet) cargado exitosamente en views.py.")
        except Exception as e:
            print(f"[WARNING] No se pudo cargar oracle_h2h_brain.pth en views.py (arquitectura distinta): {e}")
            MODELO_IA = None
    else:
        MODELO_IA = None
except Exception as e:
    print(f"Error instanciando MatchPredictionNet en views.py: {e}")
    MODELO_IA = None

# --- CARGA GLOBAL VALUE BETTING ---
DB_URL_VALUE = os.getenv("DB_URL", "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db")
try:
    DATASET_GLOBAL = FBrefPlayerDataset(db_url=DB_URL_VALUE, feature_cols=['Playing Time_Min', 'Total_Shots', 'Standard_SoT'])
    
    # MODO DIAGNÓSTICO
    print(f"DEBUG: Registros en Dataset: {len(DATASET_GLOBAL)}")
    if len(DATASET_GLOBAL) > 0:
        print(f"DEBUG: Ejemplo de jugador en DB: {DATASET_GLOBAL.metadata.iloc[0]['nombre_jugador']}")
        
    MODELO_VALUE = PlayerPropNet(input_dim=3)
    ruta_modelo = os.path.join(os.path.dirname(__file__), '..', 'modelo_base.pth')
    if os.path.exists(ruta_modelo):
        MODELO_VALUE.load_state_dict(torch.load(ruta_modelo, map_location=torch.device('cpu')))
        MODELO_VALUE.eval()
        print("[OK] Red Neuronal (PlayerPropNet) Cacheada Exitosamente.")
    else:
        print(f"[WARNING] No ubicamos los pesos del modelo en: {ruta_modelo}")
        MODELO_VALUE = None
except Exception as e:
    DATASET_GLOBAL = None
    MODELO_VALUE = None

# --- CARGA DEL ORÁCULO DE PARTIDOS (Random Forest) ---
try:
    match_model_path = os.path.join(os.path.dirname(__file__), '..', 'match_oracle_rf.pkl')
    # Fallback to root directly
    if not os.path.exists(match_model_path):
        match_model_path = 'match_oracle_rf.pkl'
        
    MATCH_MODEL = joblib.load(match_model_path)
    engine_match = create_engine(DB_URL_VALUE)
    print("[OK] Motor Random Forest de Main Market (Match) cargado Exitosamente.")
except Exception as e:
    print(f"[WARNING] No ubicamos el Cerebro RandomForest: {e}")
    MATCH_MODEL = None
    engine_match = None

# 4. FUNCIÓN DE INFERENCIA DE LA IA
def predecir_con_pytorch(partido):
    if not MODELO_IA:
        return 33.3, 33.3, 33.3 
        
    input_tensor = torch.FloatTensor([[
        float(partido.local.prom_goles), float(partido.local.prom_tiros_puerta), float(partido.local.prom_corners),
        float(partido.visitante.prom_goles), float(partido.visitante.prom_tiros_puerta), float(partido.visitante.prom_corners)
    ]])
    
    with torch.no_grad(): 
        salida = MODELO_IA(input_tensor)
        probs = torch.nn.functional.softmax(salida, dim=1)[0].tolist()
        
    # El target map de MatchDataset: Empate(0), Local(1), Visita(2)
    return round(probs[1]*100, 1), round(probs[0]*100, 1), round(probs[2]*100, 1)

# 5. VISTAS DE DJANGO
def home(request):
    try:
        hoy = timezone.now().date()
        from .models import DailySchedule
        partidos_hoy = DailySchedule.objects.filter(match_date=hoy)
        
        todays_schedule = {'soccer': [], 'nba': [], 'mlb': []}
        import random
        
        if partidos_hoy.exists():
            for p in partidos_hoy:
                # Format time string gracefully
                time_str = p.start_time.strftime('%H:%M') if p.start_time else '--:--'
                
                # Fetching real odds requires odds integration, setting to 0 for now
                if p.sport == 'soccer':
                    todays_schedule['soccer'].append({
                        'time': time_str, 'home': p.home_team, 'away': p.away_team,
                        'odds_1': 0, 
                        'odds_x': 0, 
                        'odds_2': 0
                    })
                elif p.sport == 'nba':
                    todays_schedule['nba'].append({
                        'time': time_str, 'home': p.home_team, 'away': p.away_team,
                        'odds_h': 0, 
                        'odds_a': 0
                    })
                elif p.sport == 'mlb':
                    todays_schedule['mlb'].append({
                        'time': time_str, 'home': p.home_team, 'away': p.away_team,
                        'odds_h': 0, 
                        'odds_a': 0
                    })
        else:
            print("DailySchedule empty for today. No matches to show.")
            
    except Exception as e:
        print(f"Error fetching schedule: {e}")
    
    context = {'active_tab': 'chatbot', 'schedule': todays_schedule} # default state
    
    if request.method == 'POST':
        context['active_tab'] = 'scanner'
        
        jugador = request.POST.get('jugador', '').strip()
        try:
            linea_casino = float(request.POST.get('linea_casino', 0.0))
        except ValueError:
            context['error'] = "Debes proveer un número decimal válido para la línea."
            return render(request, 'dashboard_futurista.html', context)
        
        if not DATASET_GLOBAL or not MODELO_VALUE:
            context['error'] = "El motor algorítmico no está montado en la RAM."
            return render(request, 'dashboard_futurista.html', context)
            
        if len(DATASET_GLOBAL) == 0:
            context['error'] = "Error Crítico: El sistema de IA no ha cargado datos. Verifica la conexión."
            return render(request, 'dashboard_futurista.html', context)
            
        metadata = DATASET_GLOBAL.metadata
        jugador_normalizado = jugador.lower().strip()
        
        jugador_encontrado = False
        idx_encontrado = None
        
        for i, nombre_db in metadata['nombre_jugador'].items():
            if pd.isna(nombre_db): continue
            if jugador_normalizado in str(nombre_db).lower():
                jugador_encontrado = True
                idx_encontrado = i
                break
        
        if not jugador_encontrado:
            context['error'] = f'El jugador "{jugador}" no existe en la base de datos activa.'
            return render(request, 'dashboard_futurista.html', context)
            
        nombre_real = metadata.loc[idx_encontrado, 'nombre_jugador']
        equipo = metadata.loc[idx_encontrado, 'team_name']
        features_tensor, _ = DATASET_GLOBAL[idx_encontrado]
        features_tensor = features_tensor.float()
        
        with torch.no_grad():
            predict_tensor = MODELO_VALUE(features_tensor.unsqueeze(0))
            ia_predict = round(predict_tensor.item(), 2)
            
        edge = round(ia_predict - linea_casino, 2)
        if edge >= 1.0:
            recomendacion = "OVER (Altas)"
            color = "success"
        elif edge <= -1.0:
            recomendacion = "UNDER (Bajas)"
            color = "success"
        else:
            recomendacion = "NO BET"
            color = "warning"
            
        resultado = {
            'ia_predict': ia_predict, 'edge': edge, 'recomendacion': recomendacion,
            'nombre_real': nombre_real, 'equipo': equipo, 'linea_casino': linea_casino, 'color': color
        }
        
        print(f"=== DEBUG BACKEND: {resultado} ===")
        context['resultado'] = resultado
        
    return render(request, 'dashboard_futurista.html', context)

@csrf_exempt
def chatbot_web(request):
    if request.method == "POST":
        data = json.loads(request.body)
        msg = data.get("message", "").lower()
        
        res_l, res_e, res_v = 0, 0, 0
        ctx = "No encontré datos históricos suficientes para procesar a tu oponente mediante nuestro modelo matemático."
        equipo_encontrado = None

        equipos_encontrados = []
        # Buscar equipos iterando todos (ordenado por length inverso para evitar match parcial if needed, pero all() está bien)
        for eq in Equipos.objects.all():
            if eq.nombre.lower() in msg:
                equipos_encontrados.append(eq)
        
        widget_html = ""
        
        class HipoteticoPartido:
            def __init__(self, local, visitante):
                self.local = local; self.visitante = visitante

        if len(equipos_encontrados) >= 2:
            eq1 = equipos_encontrados[0]
            eq2 = equipos_encontrados[1]
            res_l, res_e, res_v = predecir_con_pytorch(HipoteticoPartido(eq1, eq2))
            ctx = f"Predicción Neural H2H: {eq1.nombre} {res_l}% | Empate {res_e}% | {eq2.nombre} {res_v}%"
            
            widget_html = f'''
            <div class="result-box" style="margin-top:15px; padding:1rem; background:rgba(0,0,0,0.4);">
                <div style="text-align:center; font-family:'Space Grotesk'; font-size:1.1rem; color:#fff; border-bottom:1px dashed rgba(255,255,255,0.2); padding-bottom:10px; margin-bottom:10px;">
                    Simulación H2H: {eq1.nombre} vs {eq2.nombre}
                </div>
                <div class="metrics-grid" style="grid-template-columns: 1fr 1fr 1fr; margin-bottom:0; gap:0.5rem;">
                    <div class="metric-card" style="padding:0.8rem;"><div class="metric-label" style="font-size:0.6rem;">{eq1.nombre}</div><div class="metric-value highlight" style="font-size:1.3rem;">{res_l}%</div></div>
                    <div class="metric-card" style="padding:0.8rem;"><div class="metric-label" style="font-size:0.6rem;">Empate</div><div class="metric-value" style="font-size:1.3rem; color:#94A3B8;">{res_e}%</div></div>
                    <div class="metric-card" style="padding:0.8rem;"><div class="metric-label" style="font-size:0.6rem;">{eq2.nombre}</div><div class="metric-value" style="font-size:1.3rem; color:#f59e0b; text-shadow:0 0 10px rgba(245,158,11,0.5);">{res_v}%</div></div>
                </div>
            </div>'''
            
        elif len(equipos_encontrados) == 1:
            equipo_encontrado = equipos_encontrados[0]
            p = Partido.objects.filter(Q(local=equipo_encontrado) | Q(visitante=equipo_encontrado)).order_by('-fecha').first()
            if p:
                res_l, res_e, res_v = predecir_con_pytorch(p)
                ctx = f"Predicción Histórica Neural: {p.local.nombre} {res_l}% | Empate {res_e}% | {p.visitante.nombre} {res_v}%"
                
                widget_html = f'''
                <div class="result-box" style="margin-top:15px; padding:1rem; background:rgba(0,0,0,0.4);">
                    <div style="text-align:center; font-family:'Space Grotesk'; font-size:1.1rem; color:#fff; border-bottom:1px dashed rgba(255,255,255,0.2); padding-bottom:10px; margin-bottom:10px;">
                        Último Partido: {p.local.nombre} vs {p.visitante.nombre}
                    </div>
                    <div class="metrics-grid" style="grid-template-columns: 1fr 1fr 1fr; margin-bottom:0; gap:0.5rem;">
                        <div class="metric-card" style="padding:0.8rem;"><div class="metric-label" style="font-size:0.6rem;">{p.local.nombre}</div><div class="metric-value highlight" style="font-size:1.3rem;">{res_l}%</div></div>
                        <div class="metric-card" style="padding:0.8rem;"><div class="metric-label" style="font-size:0.6rem;">Empate</div><div class="metric-value" style="font-size:1.3rem; color:#94A3B8;">{res_e}%</div></div>
                        <div class="metric-card" style="padding:0.8rem;"><div class="metric-label" style="font-size:0.6rem;">{p.visitante.nombre}</div><div class="metric-value" style="font-size:1.3rem; color:#f59e0b; text-shadow:0 0 10px rgba(245,158,11,0.5);">{res_v}%</div></div>
                    </div>
                    <div style="text-align:center; margin-top:10px; color:#94A3B8; font-size:0.75rem;">Tip: Ingresa dos equipos para un análisis H2H hipotético.</div>
                </div>'''

        # Llamada a IA Cognitiva (Gemini)
        texto_respuesta = ""
        if client:
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=f"Eres analista deportivo de It's Coming. Data Neural: {ctx}. Pregunta humana: {msg}. Da tu pick justificado brevemente de la estadística sin alucinar."
                )
                texto_respuesta = response.text
            except Exception as e:
                texto_respuesta = f"*(Aviso del Sistema: Agente de Lenguaje ocupado. Procesando sólo análisis predictivo Neural crudo a continuación).*"
        else:
            texto_respuesta = f"*Aviso: Generador LLM Desconectado (Falta GEMINI_API_KEY).*"
        
        return JsonResponse({
            "reply": texto_respuesta, 
            "widget": widget_html,
            "prob": res_l, 
            "confidence": "ALTA" if max(res_l, res_v) > 65 else "MEDIA"
        })
            
    return render(request, 'dashboard_futurista.html')

def chatbot_prediccion(request, nombre_equipo=None, partido_id=None):
    return JsonResponse({"status": "active"})

def match_scanner_view(request):
    context = {}
    
    if request.method == 'POST':
        home_team = request.POST.get('home_team', '').strip()
        away_team = request.POST.get('away_team', '').strip()
        
        try:
            odd_home = float(request.POST.get('odd_home', 0.0))
            odd_draw = float(request.POST.get('odd_draw', 0.0))
            odd_away = float(request.POST.get('odd_away', 0.0))
        except ValueError:
            context['error'] = "Las cuotas ingresadas son inválidas."
            return render(request, 'match_scanner.html', context)
            
        if not MATCH_MODEL or not engine_match:
            context['error'] = "El modelo de probabilidad (Random Forest) no está cargado en el clúster."
            return render(request, 'match_scanner.html', context)
            
        # 1. Extracción de Form de ML_MATCH_FEATURES
        try:
            # HOME TEAM
            query_home = f"SELECT home_team, away_team, home_form_gf, home_form_ga, away_form_gf, away_form_ga FROM ml_match_features WHERE home_team = '{home_team}' OR away_team = '{home_team}' ORDER BY date DESC LIMIT 1"
            df_h = pd.read_sql(query_home, engine_match)
            if df_h.empty:
                context['error'] = f"No hay registro histórico en BD para el local: {home_team}."
                return render(request, 'match_scanner.html', context)
            r_h = df_h.iloc[0]
            if r_h['home_team'] == home_team:
                home_gf, home_ga = float(r_h['home_form_gf']), float(r_h['home_form_ga'])
            else:
                home_gf, home_ga = float(r_h['away_form_gf']), float(r_h['away_form_ga'])
                
            # AWAY TEAM
            query_away = f"SELECT home_team, away_team, home_form_gf, home_form_ga, away_form_gf, away_form_ga FROM ml_match_features WHERE home_team = '{away_team}' OR away_team = '{away_team}' ORDER BY date DESC LIMIT 1"
            df_a = pd.read_sql(query_away, engine_match)
            if df_a.empty:
                context['error'] = f"No hay registro histórico en BD para el visitante: {away_team}."
                return render(request, 'match_scanner.html', context)
            r_a = df_a.iloc[0]
            if r_a['home_team'] == away_team:
                away_gf, away_ga = float(r_a['home_form_gf']), float(r_a['home_form_ga'])
            else:
                away_gf, away_ga = float(r_a['away_form_gf']), float(r_a['away_form_ga'])
                
        except Exception as e:
            context['error'] = f"Error DB al aislar la métrica 'Form': {str(e)}"
            return render(request, 'match_scanner.html', context)

        # 2. Vector de Predicción
        X = pd.DataFrame([{
            'home_form_gf': home_gf,
            'home_form_ga': home_ga,
            'away_form_gf': away_gf,
            'away_form_ga': away_ga
        }])
        
        # 3. Predict Proba
        probabilities = MATCH_MODEL.predict_proba(X)[0]
        proba_map = {cls: prob for cls, prob in zip(MATCH_MODEL.classes_, probabilities)}
        
        ia_prob_draw = proba_map.get(0, 0.0)
        ia_prob_home = proba_map.get(1, 0.0)
        ia_prob_away = proba_map.get(2, 0.0)

        # 4. Inferencia Lógica (Algoritmo Cuantitativo de Implied Odds)
        implied_home = 1 / odd_home if odd_home > 0 else 0
        implied_draw = 1 / odd_draw if odd_draw > 0 else 0
        implied_away = 1 / odd_away if odd_away > 0 else 0
        
        edge_home = (ia_prob_home - implied_home) * 100
        edge_draw = (ia_prob_draw - implied_draw) * 100
        edge_away = (ia_prob_away - implied_away) * 100
        
        # 5. Recomendación Estricta
        edges = [('LOCAL', edge_home, odd_home), ('EMPATE', edge_draw, odd_draw), ('VISITANTE', edge_away, odd_away)]
        edges.sort(key=lambda x: x[1], reverse=True)
        best_bet = edges[0]
        
        if best_bet[1] > 0:
            recomendacion = f"🚀 ¡VALUE BET DETECTADA! -> APOSTAR AL {best_bet[0]} a Cuota {best_bet[2]} (Alpha Edge: +{best_bet[1]:.2f}%)"
        else:
            recomendacion = "❌ NO BET (Márgen Insuficiente, Riesgo Intolerable en el Mercado Actual)"
            
        context['resultado_partido'] = {
            'home_team': home_team, 'away_team': away_team,
            'ia_home': round(ia_prob_home * 100, 2), 'ia_draw': round(ia_prob_draw * 100, 2), 'ia_away': round(ia_prob_away * 100, 2),
            'casino_home': round(implied_home * 100, 2), 'casino_draw': round(implied_draw * 100, 2), 'casino_away': round(implied_away * 100, 2),
            'edge_home': round(edge_home, 2), 'edge_draw': round(edge_draw, 2), 'edge_away': round(edge_away, 2),
            'recomendacion': recomendacion,
            'hay_valor': best_bet[1] > 0
        }

    return render(request, 'match_scanner.html', context)

@csrf_exempt
def chat_api_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_input = data.get("message", "")
            
            # Importar dinámicamente el pipeline LCEL
            from src.services.chatbot_agent import llm_con_herramientas, diccionario_herramientas
            from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
            
            # Iniciar contexto e historial
            SYSTEM_PROMPT = (
                "Eres 'El Oráculo', un Analista Quant Veterano de Wall Street aplicado a deportes. "
                "Hablas de tú a tú con el usuario como si fuera tu colega del trading floor (ej. 'Entendido, colega', 'Revisando las matrices...'). "
                "No uses frases de IA ni pidas disculpas. Sé directo, afilado y conversacional.\n\n"
                "REGLA DE ORQUESTACIÓN 360º: Cuando el usuario pida análisis de un partido, estás OBLIGADO a invocar TODAS "
                "las herramientas (Partido, Totales, Secundarios y Player Props) e integrarlas en UNA sola respuesta estructurada.\n\n"
                "Formatea usando Markdown limpio, usando negritas para el Edge. OBLIGATORIO: Utiliza estos emojis al lado de tus proyecciones: "
                "⚽ (para Goles), 🚩 (para Córners), 🟨 (para Tarjetas), 🎯 (para Player Props)."
            )
            mensajes = [SystemMessage(content=SYSTEM_PROMPT)]
            mensajes.append(HumanMessage(content=user_input))
            
            # 1. Invocación inicial de la IA
            respuesta_ia = llm_con_herramientas.invoke(mensajes)
            mensajes.append(respuesta_ia)
            
            # 2. IA decide invocar herramienta(s) si detecta la necesidad
            if respuesta_ia.tool_calls:
                for tool_call in respuesta_ia.tool_calls:
                    nombre = tool_call["name"]
                    argumentos = tool_call["args"]
                    # Ejecuta función python real
                    resultado_python = diccionario_herramientas[nombre].invoke(argumentos)
                    mensajes.append(ToolMessage(content=str(resultado_python), tool_call_id=tool_call["id"]))
                
                # 3. Respuesta final con los datos insertados
                respuesta_final = llm_con_herramientas.invoke(mensajes)
                respuesta_texto = respuesta_final.content
            else:
                respuesta_texto = respuesta_ia.content

            return JsonResponse({"reply": respuesta_texto})
            
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
            
    return JsonResponse({"error": "Método Inválido"}, status=405)

def chat_view(request):
    return render(request, 'chat.html')