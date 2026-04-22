import pandas as pd
import joblib
from sqlalchemy import create_engine
import numpy as np
from scipy.stats import poisson

# Cargar el oráculo de regresión globalmente en memoria
MODEL_PATH = 'totals_oracle_xgb.pkl'
try:
    model = joblib.load(MODEL_PATH)
except Exception as e:
    print(f"Error al cargar el modelo: {e}. Asegúrate de haber completado la fase de entrenamiento.")
    model = None

# Configuración de BD
DB_URL = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
engine = create_engine(DB_URL)

def extract_latest_team_form(team_name):
    """
    Busca cronológicamente el último partido registrado del equipo (sea local o visitante)
    para extraer su forma macro de Goles a Favor (GF) y Goles en Contra (GA).
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

def analyze_totals(home_team, away_team, odd_over_25, odd_under_25):
    """
    Motor Cuantitativo de Totales (Over/Under 2.5): 
    Extrae estado, predice xG global con Regresión, y usa Transformada de Poisson 
    para calcular probabilidades de casino vs. IA.
    """
    if model is None:
        return
        
    print(f"\n===========================================================")
    print(f"🎯 TOTALS VALUE SCANNER: {home_team} (L) vs {away_team} (V)")
    print(f"===========================================================")
    
    # 1. Extracción de Estado (Form)
    try:
        home_gf, home_ga = extract_latest_team_form(home_team)
        away_gf, away_ga = extract_latest_team_form(away_team)
    except Exception as e:
        print(f"Error Extracción: {e}")
        return
        
    print(f"[ESTADO] {home_team} Form (GF {home_gf:.2f} | GA {home_ga:.2f})")
    print(f"[ESTADO] {away_team} Form (GF {away_gf:.2f} | GA {away_ga:.2f})")

    # 2. Vector X de Características
    X = pd.DataFrame([{
        'home_form_gf': home_gf,
        'home_form_ga': home_ga,
        'away_form_gf': away_gf,
        'away_form_ga': away_ga
    }])
    
    # 3. Predicción Regresiva (xG Match Absoluto)
    expected_goals = float(model.predict(X)[0])
    print(f"\n[PROYECCIÓN IA] Goles Esperados (xG Global): {expected_goals:.2f} goles")
    
    # 4. Distribución de Poisson (Magia Cuantitativa a O/U 2.5)
    # Poisson.cdf(k, mu) devuelve la prob. acumulada de que la variable sea <= k (es decir: 0, 1 o 2 goles).
    prob_under_25 = poisson.cdf(2, expected_goals)
    prob_over_25 = 1 - prob_under_25

    # 5. Cálculo Implícito del Casino
    implied_over = 1 / odd_over_25 if odd_over_25 > 0 else 0
    implied_under = 1 / odd_under_25 if odd_under_25 > 0 else 0
    
    # 6. Cálculo del Edge
    edge_over = (prob_over_25 - implied_over) * 100
    edge_under = (prob_under_25 - implied_under) * 100

    # 7. Reporte Financiero de Mercado
    print("\n[MERCADO] ------ LÍNEA 2.5: IA vs CASINO ------")
    print(f"OVER  2.5 | IA: {prob_over_25 * 100:>5.1f}% | Casino: {implied_over * 100:>5.1f}% (Cuota {odd_over_25}) -> Edge: {edge_over:>6.2f}%")
    print(f"UNDER 2.5 | IA: {prob_under_25 * 100:>5.1f}% | Casino: {implied_under * 100:>5.1f}% (Cuota {odd_under_25}) -> Edge: {edge_under:>6.2f}%")
    
    print("\n[SISTEMA] ------ RECOMENDACIÓN FINAL OVER/UNDER ------")
    found_value = False
    
    if edge_over > 0:
        print(f"✅ VALUE BET DETECTADA: Apostar 💰 OVER 2.5 a cuota {odd_over_25} (Margen: +{edge_over:.2f}%)")
        found_value = True
    if edge_under > 0:
        print(f"✅ VALUE BET DETECTADA: Apostar 💰 UNDER 2.5 a cuota {odd_under_25} (Margen: +{edge_under:.2f}%)")
        found_value = True

    if not found_value:
        print("❌ NO BET: Las líneas del casino no ofrecen valor positivo. Evitar mercado de Totales.")
    print("===========================================================\n")


if __name__ == "__main__":
    # Simulación Analítica
    print("Iniciando Módulo Cuantitativo de Totales (Poisson Method)...")
    
    # Clásico de la Bundesliga de alta varianza goleadora
    analyze_totals(
        home_team='Bayern Munich', 
        away_team='Dortmund', 
        odd_over_25=1.65, 
        odd_under_25=2.20
    )
    
    # Simulación secundaria de equipos defensivos
    analyze_totals(
        home_team='Juventus', 
        away_team='Milan', 
        odd_over_25=2.15, 
        odd_under_25=1.66
    )
