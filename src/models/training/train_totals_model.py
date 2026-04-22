import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
import joblib
from sqlalchemy import create_engine
import time

def train_totals_model():
    start_time = time.time()
    print("Iniciando entrenamiento del Oráculo de Totales (XGBRegressor)...")
    
    # 1. Carga de Datos
    db_url = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
    engine = create_engine(db_url)
    
    print("Leyendo y cronologizando la matriz de features 'ml_match_features'...")
    df = pd.read_sql("SELECT * FROM ml_match_features ORDER BY date ASC", engine)
    
    if len(df) == 0:
        print("Error Crítico: El dataset está vacío. Abortando entrenamiento.")
        return
        
    print(f"Total de registros históricos: {len(df)}")
    
    # 2. Definición de Variables y Target (Mercado Over/Under)
    features = ['home_form_gf', 'home_form_ga', 'away_form_gf', 'away_form_ga']
    target = 'total_goals'
    
    # Asegurar la pureza del dato de entrenamiento
    df = df.dropna(subset=features + [target]).reset_index(drop=True)
    
    X = df[features]
    y = df[target]

    # 3. Split Cronológico (Data Leakage Defense)
    print("\nAplicando Time-Series Split manual (80% Pasado / 20% Futuro)...")
    split_index = int(len(df) * 0.8)
    
    X_train = X.iloc[:split_index]
    y_train = y.iloc[:split_index]
    
    X_test = X.iloc[split_index:]
    y_test = y.iloc[split_index:]
    
    print(f"Data en Train: {len(X_train)} partidos.")
    print(f"Data en Test: {len(X_test)} partidos.")

    # 4. Entrenamiento del Modelo Regresivo Parametrizado
    print("\nInicializando algoritmo XGBRegressor (Gradient Boosting)...")
    # objective='reg:squarederror' óptimo para regresiones numéricas estelares
    model = xgb.XGBRegressor(
        n_estimators=300, 
        learning_rate=0.05, 
        max_depth=4, 
        subsample=0.8, 
        colsample_bytree=0.8, 
        random_state=42, 
        objective='reg:squarederror'
    )
    
    print("Iniciando fiteo numérico continuo...")
    model.fit(X_train, y_train)
    
    # 5. Evaluación Numérica
    print("\nEvaluando margen de error cruzando contra el futuro invisible (Test Data)...")
    y_pred = model.predict(X_test)
    
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    
    print("\n================== METRICS REPORT ==================")
    print(f"MAE (Mean Absolute Error): {mae:.3f}")
    print(f"RMSE (Root Mean Squared Error): {rmse:.3f}\n")
    print("--- ¿Qué significa esto en Matemáticas de Apuestas? ---")
    print(f"El Error Absoluto Medio (MAE) indica que, en promedio, tu IA se equivoca por")
    print(f"tan solo +/- {mae:.2f} goles al predecir el total del marcador final.")
    print("Si predice 2.5 y el margen es bajo, estás viendo una mina de oro en Over/Under.")
    print("====================================================")
    
    # 6. Almacenamiento Criógenico Global
    model_path = 'totals_oracle_xgb.pkl'
    joblib.dump(model, model_path)
    print(f"\n¡Cerebro Regresivo OVER/UNDER exportado con éxito en: {model_path}!")
    
    end_time = time.time()
    print(f"Ciclo Machine Learning finalizado en: {end_time - start_time:.2f} segundos.")

if __name__ == "__main__":
    train_totals_model()
