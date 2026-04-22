import sys
import os

# Agregamos la ruta del proyecto para que Python reconozca 'src' como un módulo válido
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import streamlit as st
import torch
import pandas as pd

from src.models.datasets.fbref_player_dataset import FBrefPlayerDataset
from src.models.networks.player_prop_net import PlayerPropNet

# Configuración Inicial de la Página
st.set_page_config(page_title="It's Coming AI", layout="wide")

@st.cache_resource
def load_system():
    """
    Carga el Dataset híbrido y los pesos del Modelo pre-entrenado a la memoria RAM 
    (1 sola vez) para maximizar la velocidad de la UI.
    """
    DB_URL = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
    feature_cols = ['Playing Time_Min', 'Total_Shots', 'Standard_SoT']
    
    # Instanciamos la base de datos
    dataset = FBrefPlayerDataset(db_url=DB_URL, feature_cols=feature_cols)
    
    # Cargamos el modelo
    model = PlayerPropNet(input_dim=3)
    
    # Se estipula que el dashboard se ejecute desde la raíz donde habita 'modelo_base.pth'
    model_path = "modelo_base.pth"
    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
        model.eval()
    else:
        st.error(f"[ALERTA CRÍTICA] No se encontró el archivo de pesos: '{model_path}'. Asegúrate de haber entrenado el modelo.")
        return None, None
        
    return dataset, model

def get_prediction(player_name, model, dataset):
    """
    Motor local de búsqueda e Inferencia
    (Basado en la lógica predictiva original algorítmica).
    """
    mask = dataset.metadata['nombre_jugador'].str.contains(player_name, case=False, na=False)
    matches = dataset.metadata[mask]
    
    if matches.empty:
        return None
        
    idx = matches.index[0]
    real_name = matches.loc[idx, 'nombre_jugador']
    team_name = matches.loc[idx, 'team_name']
    
    features_tensor, _ = dataset[idx]
    
    with torch.no_grad():
        prediction_tensor = model(features_tensor.unsqueeze(0))
        predicted_goals = round(prediction_tensor.item(), 2)
        
    return real_name, team_name, predicted_goals

# --- UI Principal del Dashboard ---
st.title("⚽ It's Coming AI - Escáner de Value Betting")
st.markdown("Sistema Cuantitativo para detección en tiempo real de ineficiencias o **Edges** contra las casas de apuestas.")
st.divider()

# Invocamos la caché de nuestros modelos
dataset, model = load_system()

if dataset is not None and model is not None:
    # Maquetación en Dos Columnas: Inputs / Resultados
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("Entrada de Mercado (Casino)")
        
        player_name = st.text_input("Ingresa el Nombre del Jugador", value="Kylian Mbappé")
        casino_line = st.number_input("Establece la Línea del Casino (Goles)", value=10.5, step=0.5)
        
        # Botón Accionable
        scan_button = st.button("Analizar Valor Estratégico", type="primary", use_container_width=True)

    with col2:
        st.subheader("Resultados de Inferencia (IA)")
        
        if scan_button:
            if not player_name:
                st.warning("⚠️ ¿Podrías proporcionar el nombre del jugador para iniciar el análisis?")
            else:
                with st.spinner("Computando inferencia de red neuronal en BD PostgreSQL..."):
                    result = get_prediction(player_name, model, dataset)
                    
                    if result is None:
                        st.error(f"❌ Sin registros base en data. No se localiza al jugador: '{player_name}'.")
                    else:
                        real_name, team, ia_prediction = result
                        edge = round(ia_prediction - casino_line, 2)
                        
                        st.markdown(f"**Identidad Verificada**: {real_name} (*{team}*)")
                        
                        # Panel de Métricas Inteligentes Numéricas
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Proyección IA", ia_prediction)
                        m2.metric("Línea Casino", casino_line)
                        m3.metric("Borde [Edge]", f"{'+' if edge > 0 else ''}{edge}")
                        
                        st.divider()
                        
                        # Señales de acción para el inversor algorítmico (Recomendaciones)
                        if edge >= 1.0:
                            st.success("🔥 **APUESTA DE ALTO VALOR RECOMENDADA: OVER (ALTAS)**")
                        elif edge <= -1.0:
                            st.success("🔥 **APUESTA DE ALTO VALOR RECOMENDADA: UNDER (BAJAS)**")
                        else:
                            st.warning("⚠️ **NO BET** - Línea extremadamente ajustada por el casino, riesgo elevado.")
else:
    st.info("Espera. Los modelos no están en memoria...")
