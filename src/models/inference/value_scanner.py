import torch
import pandas as pd

# Reutilizamos las funciones probadas de inferencia de nuestro script predict.py
from src.models.inference.predict import load_model, predict_player_goals
from src.models.datasets.fbref_player_dataset import FBrefPlayerDataset

def analyze_bet(player_name: str, casino_line: float, model, dataset) -> dict:
    """
    Analiza una línea de apuestas (goles). Compara el 'casino_line' del mercado contra
    nuestra IA algorítmica para detectar ineficiencias o valor esperado (Edge).
    """
    prediction_result = predict_player_goals(player_name, model, dataset)
    
    if prediction_result is None:
        return {
            'status': 'error',
            'message': "No se encontró registro estadístico activo para este jugador."
        }
        
    real_name, team_name, proj_goals = prediction_result
    
    # Cálculo del Edge: Cuánta es la diferencia entre el casino y nuestra IA evaluadora
    edge = round(proj_goals - casino_line, 2)
    
    # Determinamos la Recomendación basada en reglas numéricas duras
    if proj_goals > (casino_line + 1.0):
        recommendation = "OVER"
    elif proj_goals < (casino_line - 1.0):
        recommendation = "UNDER"
    else:
        recommendation = "NO BET"
        
    return {
        'status': 'success',
        'real_name': real_name,
        'team': team_name,
        'ia_prediction': proj_goals,
        'casino_line': casino_line,
        'edge': edge,
        'recommendation': recommendation
    }

if __name__ == "__main__":
    print("-" * 75)
    print("ESCÁNER DE VALUE BETTING - IDENTIFICACIÓN DE BORDES (EDGES)")
    print("-" * 75)

    # 1. Rutas y configuración de base de datos
    DB_URL = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
    feature_cols = ['Playing Time_Min', 'Total_Shots', 'Standard_SoT']
    
    try:
        # Cargamos nuestro DataWarehouse PostgreSQL y modelo neuronal
        print("[*] Levando Dataset Híbrido e ingiriendo datos...")
        dataset = FBrefPlayerDataset(db_url=DB_URL, feature_cols=feature_cols)
        
        print("[*] Arrancando núcleo predictivo neuronal PyTorch (modelo_base.pth)...")
        model = load_model('modelo_base.pth', input_dim=3)
        
        print("[✔] Escáner listo. Evaluando lista de mercado de prueba...\n")
        
        # 2. Diccionario del mercado (simulado)
        apuestas_mercado = [
            {'jugador': 'Kylian Mbappé', 'linea': 24.5}, 
            {'jugador': 'Erling Haaland', 'linea': 18.5}, 
            {'jugador': 'Vinicius Júnior', 'linea': 16.5}
        ]
        
        # 3. Impresión del Reporte Financiero/Quants
        print(f"{'JUGADOR':<20} | {'CASINO LINE':<12} | {'IA PREDICT':<10} | {'EDGE':<6} | {'RECOMENDACIÓN':<15}")
        print("-" * 75)
        
        for apuesta in apuestas_mercado:
            jugador_buscar = apuesta['jugador']
            linea = apuesta['linea']
            
            report = analyze_bet(jugador_buscar, linea, model, dataset)
            
            if report['status'] == 'success':
                p_name = f"{report['real_name'][:18]:<20}"
                c_line = f"{report['casino_line']:<12}"
                i_pred = f"{report['ia_prediction']:<10}"
                
                # Resaltamos el signo en el Edge (+/-)
                str_edge = f"+{report['edge']}" if report['edge'] > 0 else f"{report['edge']}"
                e_val  = f"{str_edge:<6}"
                
                r_act  = f"{report['recommendation']:<15}"
                
                print(f"{p_name} | {c_line} | {i_pred} | {e_val} | {r_act}")
            else:
                print(f"{jugador_buscar[:18]:<20} | [Error: {report['message']}]")
                
        print("-" * 75)
        
    except FileNotFoundError:
        print("\n[CRÍTICO] Falta el archivo 'modelo_base.pth'. Entrena la red antes de escanear apuestas.")
    except Exception as e:
        print(f"\n[ERROR FATAL] Fallo en el sistema de validación: {e}") 
