import pandas as pd
import joblib
from sqlalchemy import create_engine
import numpy as np

# Cargar el oráculo (modelo) globalmente en memoria
MODEL_PATH = 'match_oracle_rf.pkl'
try:
    model = joblib.load(MODEL_PATH)
    # Extraer el mapeo de clases que aprendió el modelo internamente
    # Generalmente será [0., 1., 2.] -> [Draw, Home, Away]
    classes = model.classes_
except Exception as e:
    print(f"Error al cargar el modelo: {e}. Asegúrate de haber completado la fase de entrenamiento.")
    model = None

# Configuración de BD
DB_URL = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
engine = create_engine(DB_URL)

def extract_latest_team_form(team_name):
    """
    Busca cronológicamente el último partido registrado del equipo (sea local o visitante)
    para extraer su forma de Goles a Favor (GF) y Goles en Contra (GA).
    """
    query = f"""
        SELECT date, home_team, away_team, 
               home_form_gf, home_form_ga, 
               away_form_gf, away_form_ga 
        FROM ml_match_features 
        WHERE home_team = '{team_name}' OR away_team = '{team_name}'
        ORDER BY date DESC 
        LIMIT 1
    """
    df = pd.read_sql(query, engine)
    
    if df.empty:
        raise ValueError(f"No hay registros matemáticos en el Data Warehouse para el equipo: {team_name}")
        
    row = df.iloc[0]
    
    # Determinar si en su último encuentro fue Local o Visitante
    if row['home_team'] == team_name:
        form_gf = float(row['home_form_gf'])
        form_ga = float(row['home_form_ga'])
    else:
        form_gf = float(row['away_form_gf'])
        form_ga = float(row['away_form_ga'])
        
    return form_gf, form_ga

def analyze_match(home_team, away_team, odd_home, odd_draw, odd_away):
    """
    Motor Cuantitativo: Extrae el estado actual, proyecta las probabilidades mediante
    predict_proba, y calcula el 'Edge' algorítmico contra el casino.
    """
    if model is None:
        return
        
    print(f"\n===========================================================")
    print(f"💰 VALUE BETTING SCANNER: {home_team} (L) vs {away_team} (V)")
    print(f"===========================================================")
    
    # 1. Extracción de Estado (Form)
    try:
        home_gf, home_ga = extract_latest_team_form(home_team)
        away_gf, away_ga = extract_latest_team_form(away_team)
    except Exception as e:
        print(f"Error Extracción: {e}")
        return
        
    print(f"[ESTADO] {home_team} Form (Últimos 5): GF {home_gf:.2f} | GA {home_ga:.2f}")
    print(f"[ESTADO] {away_team} Form (Últimos 5): GF {away_gf:.2f} | GA {away_ga:.2f}")

    # 2. Vector X de Características
    # Debe coincidir dimensionalmente con ['home_form_gf', 'home_form_ga', 'away_form_gf', 'away_form_ga']
    X = pd.DataFrame([{
        'home_form_gf': home_gf,
        'home_form_ga': home_ga,
        'away_form_gf': away_gf,
        'away_form_ga': away_ga
    }])
    
    # 3. Predicción Proba (El Oráculo)
    # probabilities será un array 2D, ej: [[0.25, 0.50, 0.25]]
    probabilities = model.predict_proba(X)[0]
    
    # Mapeo universal de las clases del RandomForest al Dominio Deportivo (.classes_ contiene el orden)
    # Por lo general: 0 es Draw, 1 es Home, 2 es Away. 
    proba_map = {cls: prob for cls, prob in zip(model.classes_, probabilities)}
    
    ia_prob_home = proba_map.get(1, 0.0)
    ia_prob_draw = proba_map.get(0, 0.0)
    ia_prob_away = proba_map.get(2, 0.0)

    # 4. Cálculo Implícito del Casino
    implied_home = 1 / odd_home
    implied_draw = 1 / odd_draw
    implied_away = 1 / odd_away
    
    # 5. Cálculo del Edge Cuantitativo
    edge_home = (ia_prob_home - implied_home) * 100
    edge_draw = (ia_prob_draw - implied_draw) * 100
    edge_away = (ia_prob_away - implied_away) * 100

    # 6. Reporte Financiero
    print("\n[MERCADO] ------ PROBABILIDADES IA vs CASINO ------")
    print(f"L | IA: {ia_prob_home * 100:>5.1f}% | Casino: {implied_home * 100:>5.1f}% (Cuota {odd_home}) -> Edge: {edge_home:>6.2f}%")
    print(f"E | IA: {ia_prob_draw * 100:>5.1f}% | Casino: {implied_draw * 100:>5.1f}% (Cuota {odd_draw}) -> Edge: {edge_draw:>6.2f}%")
    print(f"V | IA: {ia_prob_away * 100:>5.1f}% | Casino: {implied_away * 100:>5.1f}% (Cuota {odd_away}) -> Edge: {edge_away:>6.2f}%")
    
    print("\n[SISTEMA] ------ RECOMENDACIÓN FINAL DEL ORÁCULO ------")
    found_value = False
    
    if edge_home > 0:
        print(f"✅ VALUE BET DETECTADA: Apostar 💰 LOCAL ({home_team}) a cuota {odd_home} (Margen: +{edge_home:.2f}%)")
        found_value = True
    if edge_draw > 0:
        print(f"✅ VALUE BET DETECTADA: Apostar 💰 EMPATE a cuota {odd_draw} (Margen: +{edge_draw:.2f}%)")
        found_value = True
    if edge_away > 0:
        print(f"✅ VALUE BET DETECTADA: Apostar 💰 VISITANTE ({away_team}) a cuota {odd_away} (Margen: +{edge_away:.2f}%)")
        found_value = True

    if not found_value:
        print("❌ NO BET: Ninguna línea ofrece valor positivo. Evitar el mercado.")
    print("===========================================================\n")


if __name__ == "__main__":
    # Simulación Predictiva
    print("Iniciando Módulo de Inferencia Value Scanner...")
    
    # Se elige un clásico mundial. 
    analyze_match(
        home_team='Real Madrid', 
        away_team='Barcelona', 
        odd_home=2.10, 
        odd_draw=3.50, 
        odd_away=3.20
    )
    
    # Simulación secundaria de prueba
    analyze_match(
        home_team='Manchester City', 
        away_team='Arsenal', 
        odd_home=1.90, 
        odd_draw=4.20, 
        odd_away=3.80
    )
