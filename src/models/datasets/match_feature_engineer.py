import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import time

def run_feature_engineering():
    start_time = time.time()
    print("Iniciando Feature Engineering (Adaptive Team Ledger)...")
    
    db_url = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
    engine = create_engine(db_url)
    
    # 1. Lectura
    print("Leyendo tabla 'match_history_stats' desde Postgres...")
    df = pd.read_sql("SELECT * FROM match_history_stats", engine)
    
    # Detección y casting de tipos base
    cols_to_numeric = ['home_score', 'away_score']
    if 'home_xg' in df.columns and 'away_xg' in df.columns:
        cols_to_numeric.extend(['home_xg', 'away_xg'])
        
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date').reset_index(drop=True)
    print(f"Datos originales: {len(df)} partidos cargados.")
    
    # 2. Detección Dinámica de xG
    has_xg = False
    if 'home_xg' in df.columns and 'away_xg' in df.columns:
        if df['home_xg'].notna().any() and df['away_xg'].notna().any():
            has_xg = True
            
    print(f"-> Módulo de Detección Cuántica: Datos xG disponibles y viables = {has_xg}")

    # 3. Creación de Ledgers Adaptativa
    print("Construyendo el Team Ledger...")
    if has_xg:
        home_ledger = df[['date', 'home_team', 'home_score', 'away_score', 'home_xg', 'away_xg']].copy()
        home_ledger.columns = ['date', 'team', 'gf', 'ga', 'xgf', 'xga']
        
        away_ledger = df[['date', 'away_team', 'away_score', 'home_score', 'away_xg', 'home_xg']].copy()
        away_ledger.columns = ['date', 'team', 'gf', 'ga', 'xgf', 'xga']
    else:
        # Ledger resiliente ignorando xG
        home_ledger = df[['date', 'home_team', 'home_score', 'away_score']].copy()
        home_ledger.columns = ['date', 'team', 'gf', 'ga']
        
        away_ledger = df[['date', 'away_team', 'away_score', 'home_score']].copy()
        away_ledger.columns = ['date', 'team', 'gf', 'ga']
    
    # CRÍTICO - Reset de Índice
    ledger = pd.concat([home_ledger, away_ledger]).sort_values(['team', 'date']).reset_index(drop=True)
    
    # 4. Cálculo Matemático de Medias Móviles (Dinámico)
    print("Calculando el form de últimos 5 partidos con Shift(1)...")
    if has_xg:
        ledger[['form_gf', 'form_ga', 'form_xgf', 'form_xga']] = ledger.groupby('team')[['gf', 'ga', 'xgf', 'xga']].transform(
            lambda x: x.shift(1).rolling(5, min_periods=5).mean()
        )
        ledger = ledger[['date', 'team', 'form_gf', 'form_ga', 'form_xgf', 'form_xga']]
        
        # El Merge Dual
        df = pd.merge(df, ledger, left_on=['date', 'home_team'], right_on=['date', 'team'], how='left')
        df.drop('team', axis=1, inplace=True)
        df.rename(columns={'form_gf': 'home_form_gf', 'form_ga': 'home_form_ga', 'form_xgf': 'home_form_xgf', 'form_xga': 'home_form_xga'}, inplace=True)
        
        df = pd.merge(df, ledger, left_on=['date', 'away_team'], right_on=['date', 'team'], how='left')
        df.drop('team', axis=1, inplace=True)
        df.rename(columns={'form_gf': 'away_form_gf', 'form_ga': 'away_form_ga', 'form_xgf': 'away_form_xgf', 'form_xga': 'away_form_xga'}, inplace=True)

    else:
        ledger[['form_gf', 'form_ga']] = ledger.groupby('team')[['gf', 'ga']].transform(
            lambda x: x.shift(1).rolling(5, min_periods=5).mean()
        )
        ledger = ledger[['date', 'team', 'form_gf', 'form_ga']]
        
        # El Merge Dual
        df = pd.merge(df, ledger, left_on=['date', 'home_team'], right_on=['date', 'team'], how='left')
        df.drop('team', axis=1, inplace=True)
        df.rename(columns={'form_gf': 'home_form_gf', 'form_ga': 'home_form_ga'}, inplace=True)
        
        df = pd.merge(df, ledger, left_on=['date', 'away_team'], right_on=['date', 'team'], how='left')
        df.drop('team', axis=1, inplace=True)
        df.rename(columns={'form_gf': 'away_form_gf', 'form_ga': 'away_form_ga'}, inplace=True)

    # 5. Creación de Targets
    df['total_goals'] = df['home_score'] + df['away_score']
    
    def calc_result(row):
        if row['home_score'] > row['away_score']:
            return 1
        elif row['home_score'] == row['away_score']:
            return 0
        elif row['home_score'] < row['away_score']:
            return 2
        return np.nan
        
    df['result'] = df.apply(calc_result, axis=1)

    # 6. Feature Selection Dinámico
    print("Aplicando Feature Selection sobre columnas predictivas...")
    # Base robusta
    columnas_ml = [
        'league', 'season', 'date', 'home_team', 'away_team', 
        'home_score', 'away_score', 'home_form_gf', 'home_form_ga', 
        'away_form_gf', 'away_form_ga', 'total_goals', 'result'
    ]
    
    # Amplitud dimensional guiada por disponibilidad de xG
    if has_xg:
        columnas_ml.insert(7, 'home_xg')
        columnas_ml.insert(8, 'away_xg')
        columnas_ml.extend(['home_form_xgf', 'home_form_xga', 'away_form_xgf', 'away_form_xga'])
        
    df = df[columnas_ml]
    
    # CRÍTICO: Reporte de Diagnóstico
    print("\nReporte de NaNs por columna antes de limpiar:\n", df[columnas_ml].isnull().sum())
    
    # 7. Limpieza y Guardado Final
    print("\nAplicando .dropna() sobre las features seleccionadas (Depuración del Spin-up histórico)...")
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    print(f"Dataset de Features listo: {len(df)} registros limpios y viables pasaron a producción ML.")
    
    print("Guardando tensor a PostgreSQL en la tabla 'ml_match_features'...")
    df.to_sql('ml_match_features', engine, if_exists='replace', index=False)
    
    end_time = time.time()
    print(f"Éxito total. Arquitectura Data Prep finalizada en {end_time - start_time:.2f} segundos.")

if __name__ == "__main__":
    run_feature_engineering()
