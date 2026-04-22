import pandas as pd
from sqlalchemy import create_engine
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import RandomizedSearchCV
import joblib
import time

def train_match_model():
    start_time = time.time()
    print("Iniciando entrenamiento del Oráculo Predictivo (XGBoost)...")
    
    # 1. Carga de Datos
    db_url = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
    engine = create_engine(db_url)
    
    print("Leyendo y cronologizando la matriz de features 'ml_match_features'...")
    # Ordenar estrictamente por fecha dentro de la consulta SQL como medida adicional
    df = pd.read_sql("SELECT * FROM ml_match_features ORDER BY date ASC", engine)
    
    if len(df) == 0:
        print("Error Crítico: El dataset está vacío. Abortando entrenamiento.")
        return
        
    print(f"Total de registros históricos: {len(df)}")
    
    # 2. Definición de Variables y Target
    features = ['home_form_gf', 'home_form_ga', 'away_form_gf', 'away_form_ga']
    target = 'result'
    
    # Asegurar que no pasen NaNs subyacentes
    df = df.dropna(subset=features + [target]).reset_index(drop=True)
    
    X = df[features]
    y = df[target]

    # 3. Split Cronológico (Prevención letal del Data Leakage)
    print("\nAplicando Time-Series Split manual (80% Pasado / 20% Futuro)...")
    split_index = int(len(df) * 0.8)
    
    X_train = X.iloc[:split_index]
    y_train = y.iloc[:split_index].astype(int)
    
    X_test = X.iloc[split_index:]
    y_test = y.iloc[split_index:].astype(int)
    
    print(f"Data en Train (Libro Teórico): {len(X_train)} partidos.")
    print(f"Data en Test (Predicción en la Sombra): {len(X_test)} partidos.")

    # 4. Configuración de Hyperparameter Tuning (RandomizedSearchCV)
    print("\nInicializando búsqueda de Hyperparámetros para XGBClassifier...")
    
    param_dist = {
        'n_estimators': [100, 300, 500, 800],
        'learning_rate': [0.01, 0.05, 0.1, 0.2],
        'max_depth': [3, 4, 5, 6],
        'subsample': [0.7, 0.8, 0.9, 1.0],
        'colsample_bytree': [0.7, 0.8, 0.9, 1.0]
    }
    
    base_model = xgb.XGBClassifier(objective='multi:softprob', random_state=42)
    
    search = RandomizedSearchCV(
        estimator=base_model,
        param_distributions=param_dist,
        n_iter=20,
        scoring='accuracy',
        cv=3,
        verbose=2,
        random_state=42,
        n_jobs=-1
    )
    
    print("Iniciando fiteo algebraico y búsqueda (esto puede tardar unos minutos)...")
    search.fit(X_train, y_train)
    
    print("\n🔥 Mejores hiperparámetros encontrados por la IA:")
    print(search.best_params_)
    
    best_model = search.best_estimator_
    
    # 5. Evaluación Estadística
    print("\nEvaluando rendimiento en el 20% futuro invisible (Test Data)...")
    y_pred = best_model.predict(X_test)
    
    acc = accuracy_score(y_test, y_pred)
    print("\n================== METRICS REPORT ==================")
    print(f"Accuracy General (Sensibilidad Exacta): {acc:.2%}\n")
    print("Classification Report (0=Draw, 1=Home Win, 2=Away Win):")
    print(classification_report(y_test, y_pred, zero_division=0))
    print("====================================================")
    
    # 6. Almacenamiento Global
    model_path = 'match_oracle_xgb.pkl'
    joblib.dump(best_model, model_path)
    print(f"\n¡Cerebro ML guardado con éxito localmente como: {model_path}!")
    
    end_time = time.time()
    print(f"Ciclo ML completo en: {end_time - start_time:.2f} segundos.")

if __name__ == "__main__":
    train_match_model()
