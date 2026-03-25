# ⚽ It's Coming | AI-Powered Sports Analytics
![Version](https://img.shields.io/badge/Version-1.7_PRO-0ea5e9?style=for-the-badge)
![Tech](https://img.shields.io/badge/Stack-Django_|_Pandas_|_Gemini-ec4899?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-H2H_Engine_Active-00ff88?style=for-the-badge)

**It's Coming** es una plataforma de análisis predictivo de fútbol que combina modelos estadísticos clásicos con inteligencia artificial de vanguardia para detectar el "Value Edge" en el mercado de apuestas de la Premier League.

---

## 🧠 El Corazón del Modelo: Ensamble Bayesiano

Este sistema no "adivina"; calcula. Utilizamos un **Ensamble de Tres Factores** para generar probabilidades de alta precisión:

1. **Distribución de Poisson (50%)**: Analiza la eficiencia ofensiva y defensiva de la temporada actual.
   $$P(X=k) = \frac{\lambda^k e^{-\lambda}}{k!}$$
2. **Memoria Histórica H2H (30%)**: Procesa enfrentamientos directos de las últimas **5 temporadas** usando Pandas para detectar tendencias tácticas de largo plazo.
3. **Factor de Momentum (20%)**: Pondera la racha de puntos de los últimos 5 partidos para capturar el estado de forma actual.

---

## 🚀 Características Principales

* **Dashboard Futurista**: Interfaz en modo oscuro con estética *Sportsbook* diseñada en el CUCEI.
* **IA "The Oracle"**: Integración con **Gemini 2.5 Flash** que actúa como un analista experto, traduciendo datos técnicos en picks de apuestas.
* **Real-time Odds**: Conexión con **The Odds API** para comparar nuestras predicciones contra los momios reales.
* **Value Edge Discovery**: Cálculo automático para identificar cuándo la casa de apuestas está pagando más de lo que la estadística sugiere.

---

## 🛠️ Stack Tecnológico

| Tecnología | Rol en el Proyecto |
| :--- | :--- |
| **Python 3.12** | Procesamiento de datos y lógica del modelo. |
| **Django** | Arquitectura del servidor y API REST. |
| **Pandas / NumPy** | Análisis masivo de las últimas 5 temporadas. |
| **Google GenAI** | Procesamiento de lenguaje natural para el análisis experto. |
| **The Odds API** | Ingesta de momios de casas de apuestas en vivo. |

---

## 📥 Instalación y Configuración

```bash
# 1. Clonar el repositorio
git clone [https://github.com/Jaredow604/itscomming.git](https://github.com/Jaredow604/itscomming.git)
cd itscomming

# 2. Configurar el entorno virtual
python -m venv venv
./venv/Scripts/activate  # Windows
pip install -r requirements.txt

# 3. Preparar Base de Datos e Historia
python manage.py migrate
python importar_h2h.py    # Importa 5 años de datos
python actualizar_stats.py # Calcula promedios iniciales

# 4. Lanzar el Servidor
python manage.py runserver 8001
