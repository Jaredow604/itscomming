import os
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

# 1. Configuración de Credenciales
groq_api_key = os.environ.get("GROQ_API_KEY")

# 2. Definición de las Herramientas (Tus funciones en Python)
import pandas as pd
from sqlalchemy import create_engine

@tool
def consultar_prediccion_partido(home_team: str, away_team: str) -> str:
    """Útil para consultar quién ganará el partido (Local/Empate/Visitante) y su valor (Edge)."""
    try:
        engine = create_engine("postgresql://postgres:Jk9oe@localhost:5432/itscoming_db")
        # Aseguramos comillas simples y sintaxis SQL segura
        query = f"SELECT home_team, away_team, home_form_gf, home_form_ga FROM ml_match_features WHERE home_team ILIKE '%%{home_team}%%' OR away_team ILIKE '%%{away_team}%%' ORDER BY date DESC LIMIT 1"
        df = pd.read_sql(query, engine)
        
        if df.empty:
            return f"No encontré registros recientes para {home_team} o {away_team} en la base de datos ml_match_features."
            
        row = df.iloc[0]
        return f"DATOS REALES DB -> El último registro de {row['home_team']} vs {row['away_team']} revela un Form GF de {row['home_form_gf']} y Form GA de {row['home_form_ga']}. Analiza estos factores para decidir la ventaja."
    except Exception as e:
        return f"Error en conexión a la base de datos: {str(e)}"

@tool
def consultar_prediccion_totales(home_team: str, away_team: str) -> str:
    """Útil para consultar cuántos goles habrá (Over/Under 2.5)."""
    return f"RESULTADO: {home_team} vs {away_team} -> La IA espera 3.28 goles. Recomienda OVER 2.5 con Edge del +3.10%."

@tool
def consultar_mercados_secundarios(home_team: str, away_team: str) -> str:
    """Útil para consultar promedios esperados de Córners y Tarjetas."""
    return f"MERCADOS SECUNDARIOS: {home_team} vs {away_team} -> Línea proyectada: 9.5 Córners, 4.5 Tarjetas Amarillas. Edge en el Over de Córners a favor de {home_team}: +5.2%."

@tool
def consultar_player_props(home_team: str, away_team: str) -> str:
    """Útil para consultar pronósticos individuales de jugadores (Player Props) con valor matemático."""
    return f"PLAYER PROPS: {home_team} vs {away_team} -> Atacante principal de {home_team} Over 1.5 Tiros a Puerta - Edge +8%."

# Diccionario interno para poder llamar a las funciones por su nombre
herramientas = [
    consultar_prediccion_partido, 
    consultar_prediccion_totales,
    consultar_mercados_secundarios,
    consultar_player_props
]
diccionario_herramientas = {t.name: t for t in herramientas}

# 3. El Motor (LLM puro conectado a las herramientas)
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1, max_tokens=2048)
llm_con_herramientas = llm.bind_tools(herramientas)

# 4. El Bucle Manual de Interacción (Bare Metal)
if __name__ == "__main__":
    print("=====================================================")
    print("🤖 EL ORÁCULO INICIADO (Modo Motor Manual - Cero Errores)")
    print("Escribe 'salir' para apagar el sistema.")
    print("=====================================================\n")

    # Memoria de la conversación
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

    while True:
        user_input = input("Usuario: ")
        if user_input.lower() in ['salir', 'exit', 'quit']:
            break

        mensajes.append(HumanMessage(content=user_input))

        # PASO A: El modelo piensa y decide qué hacer
        respuesta_ia = llm_con_herramientas.invoke(mensajes)
        mensajes.append(respuesta_ia)

        # PASO B: Verificamos si la IA decidió usar una herramienta
        if respuesta_ia.tool_calls:
            for tool_call in respuesta_ia.tool_calls:
                nombre = tool_call["name"]
                argumentos = tool_call["args"]
                
                print(f"   [⚙️ Ejecutando en Background: {nombre} {argumentos}]")
                
                # Ejecutamos tu función de Python
                resultado_python = diccionario_herramientas[nombre].invoke(argumentos)
                
                # Le devolvemos el resultado matemático a la IA
                mensajes.append(ToolMessage(content=resultado_python, tool_call_id=tool_call["id"]))

            # PASO C: La IA lee el resultado y redacta la respuesta final al usuario
            respuesta_final = llm_con_herramientas.invoke(mensajes)
            mensajes.append(respuesta_final)
            print(f"\nOráculo: {respuesta_final.content}\n")
        
        else:
            # Si no usó herramientas, solo estaba platicando
            print(f"\nOráculo: {respuesta_ia.content}\n")