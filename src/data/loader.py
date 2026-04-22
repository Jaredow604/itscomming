import asyncio
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any
import os 

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

# Módulos del Proyecto "It's Coming"
from src.data.models import Base, Team, Match, MatchStatsNBA, MatchStatsMLB, MatchStatsFutbol, PlayerStatsNBA, PlayerStatsMLB, PlayerStatsFutbol
from src.data_ingestion.scrapers.scores365_client import Scores365Client
from src.data_processing.entity_resolver import EntityResolver
from src.data_ingestion.apis.nba_client import NBAClient
from src.data_ingestion.apis.mlb_client import MLBClient
from src.data_ingestion.scrapers.odds_scraper import OddsScraper
from src.data_ingestion.apis.soccerdata_client import SoccerDataClient

os.environ["SB_HEADLESS"] = "False"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ETL_Orchestrator")

# Cadena de conexión para PostgreSQL (Apunta a tu clúster de PyTorch DB)
# En producción, esto debe venir de variables de entorno (.env)
DB_URL = "postgresql+psycopg2}://postgres:Jk9oe@localhost:5432/itscoming_db"

def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Manejo de Pandas: Limpia nulos y estandariza tipos de datos para la ingesta SQL."""
    if df is None or df.empty:
        return df
    
    # Llenar valores nulos con 0 para mantener consistencia numérica
    df = df.fillna(0)
    
    # Remover posibles duplicados relacionales
    df = df.drop_duplicates()
    return df

def upsert_teams(session: Session, home_id: int, home_name: str, away_id: int, away_name: str):
    """
    Fase 1: Motor de Upsert (INSERT ON CONFLICT).
    Garantiza la Integridad Referencial sin afectar la constraint de Primary Key.
    """
    teams_data = [
        {"id_equipo": home_id, "nombre": home_name},
        {"id_equipo": away_id, "nombre": away_name}
    ]
    
    for team in teams_data:
        stmt = insert(Team).values(
            id_equipo=team["id_equipo"],
            nombre=team["nombre"]
        )
        # Upsert nativo: Conflictos por PK actualizan los campos

        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['id_equipo'],
            set_=dict(nombre=stmt.excluded.nombre)
        )
        session.execute(upsert_stmt)

def insert_match_core(session: Session, match_id: int, home_id: int, away_id: int, status: str = "Fixture"):
    """
    Fase 2: Inserta el Partido en el calendario transaccional matriz (Entity Root).
    """
    # Intentamos insertar directamente con lógica merge (UPSERT)
    core_match = session.merge(Match(
        id_partido=match_id,
        id_local=home_id,
        id_visitante=away_id,
        fstatus=status,
        fecha=datetime.now() # Ojo: Se puede extraer la fecha original del scraper y formatearla
    ))
    return core_match

def insert_satellite_stats(session: Session, comp_id: int, stat_dict: Dict[str, Any]):
    """
    Fase 3: Ruteo de extensión dependiente del ID de competición.
    Envía las métricas a las tablas satélites correspondientes.
    """
    if comp_id == 103: # NBA
        sat_nba = session.merge(MatchStatsNBA(
            id_partido=stat_dict.get("match_id"),
            puntos_local=int(stat_dict.get("home_points", 0)),
            puntos_visitante=int(stat_dict.get("away_points", 0)),
            rebotes_local=int(stat_dict.get("home_rebounds", 0)),
            rebotes_visitante=int(stat_dict.get("away_rebounds", 0)),
            triples_local=int(stat_dict.get("home_3_pointers", 0)),
            triples_visitante=int(stat_dict.get("away_3_pointers", 0)),
        ))
        logger.debug("Satélite insertado en DB (Stats NBA)")
        
    elif comp_id == 438: # MLB
        sat_mlb = session.merge(MatchStatsMLB(
            id_partido=stat_dict.get("match_id"),
            carreras_local=int(stat_dict.get("home_runs", 0)),
            carreras_visitante=int(stat_dict.get("away_runs", 0)),
            hits_local=int(stat_dict.get("home_hits", 0)),
            hits_visitante=int(stat_dict.get("away_hits", 0)),
            errores_local=int(stat_dict.get("home_errors", 0)),
            errores_visitante=int(stat_dict.get("away_errors", 0)),
        ))
        logger.debug("Satélite insertado en DB (Stats MLB)")
        
    elif comp_id in [7, 11, 17, 25, 67, 229]: # Futbol Elite
        sat_futbol = session.merge(MatchStatsFutbol(
            id_partido=stat_dict.get("match_id"),
            
            # Métricas Enteras (Extracción con validación dinámica)
            goles_local=int(float(stat_dict.get("home_goals", stat_dict.get("home_score", 0)))),
            goles_visitante=int(float(stat_dict.get("away_goals", stat_dict.get("away_score", 0)))),
            posesion_local=int(float(stat_dict.get("home_ball_possession", 0))),
            posesion_visitante=int(float(stat_dict.get("away_ball_possession", 0))),
            tiros_puerta_local=int(float(stat_dict.get("home_shots_on_target", 0))),
            tiros_puerta_visitante=int(float(stat_dict.get("away_shots_on_target", 0))),
            corners_local=int(float(stat_dict.get("home_corners", 0))),
            corners_visitante=int(float(stat_dict.get("away_corners", 0))),
            amarillas_local=int(float(stat_dict.get("home_yellow_cards", 0))),
            amarillas_visitante=int(float(stat_dict.get("away_yellow_cards", 0))),
            rojas_local=int(float(stat_dict.get("home_red_cards", 0))),
            rojas_visitante=int(float(stat_dict.get("away_red_cards", 0))),
            
            # Métricas ML (Esperadas)
            xg_local=float(stat_dict.get("home_expected_goals", 0.0)),
            xg_visitante=float(stat_dict.get("away_expected_goals", 0.0))
        ))
        logger.debug("Satélite insertado en DB (Stats FÚTBOL ÉLITE)")
        
    else:
        logger.warning(f"Competición detectada que todavía no cuenta con tabla satélite: (ID {comp_id})")

async def run_ingestion():
    """
    Orquestador final asincrónico E2E.
    Extrae, limpia vía Pandas y realiza transacciones atómicas a PostgreSQL mediante SQLAlchemy.
    """
    # 1. Conexión al motor de BD
    try:
        engine = create_engine(DB_URL)
        Base.metadata.create_all(engine)
        # Inserción de comodín fallback para evitar Constraint Violations
        with Session(engine) as session:
            session.merge(Team(id_equipo=-1, nombre='Rival Desconocido'))
            session.commit()
    except Exception as e:
        logger.error(f"Falla critica: No hay conexion con PostgreSQL en {DB_URL}. Error: {e}")
        return

    logger.info("Motor SQL activo. Enlazando Crawlers y APIs Oficiales...")
    client = Scores365Client()
    
    # Init Data Extensors
    client_nba = NBAClient()
    client_mlb = MLBClient()
    scraper_odds = OddsScraper()
    client_fbref = SoccerDataClient(seasons="2526")
    
    # Iteración retrospectiva (Backfill)
    for backdate_days in range(1, 6):
        target_date = (datetime.now() - timedelta(days=backdate_days)).strftime("%d/%m/%Y")
        logger.info(f"=== [ INICIANDO BARRIDO BACKFILL: {target_date} ] ===")
        
        # Rate limiting previo
        await asyncio.sleep(3)
        
        target_games = await client.get_fixtures_by_date(target_date)
        if not target_games:
            logger.info("El Crawler ha retornado 0 objetivos. Pasando al siguiente día.")
            continue

        # Transacción iterativa por evento
        for game_id in target_games:
            logger.info(f"Ingestando datos atómicos: GameID {game_id}")
            
            # A) Consumo de API
            df_h2h = client.get_h2h_by_game(game_id)
            df_stats = client.get_match_stats(game_id)
            
            if df_stats.empty:
                logger.warning(f"Partido ignorado por falta de estadísticas (Posible aplazamiento): {game_id}")
                continue
                
            # Limpieza vía Pandas
            df_stats = _clean_dataframe(df_stats)
            stat_raw = df_stats.to_dict('records')[0] 
            
            # B) Sesión Atómica DWH SQLAlchemy 2.0
            with Session(engine) as session:
                try:
                    home_id = stat_raw.get("home_team_id")
                    away_id = stat_raw.get("away_team_id")
                    
                    # Extraer el string de nombre real inyectado por el scraper fusionado
                    home_name = stat_raw.get("home_team_name", f"Team_{home_id}_Unknown")
                    away_name = stat_raw.get("away_team_name", f"Team_{away_id}_Unknown")
                    
                    # FASE 1: UPSERT con Nombres Reales Extraídos
                    upsert_teams(session, home_id, home_name, away_id, away_name)

                    # FASE 2: MATCH CORE
                    insert_match_core(session, match_id=game_id, home_id=home_id, away_id=away_id, status="Finished")
                    
                    # FASE 3: MAPEO Y SATELLITES
                    comp_id = stat_raw.get("competition_id", 103) # Dejará de ser default cuando extraigas de la DB
                    
                    # Inferimos del H2H temporalmente ya que el H2H en tu sistema trae 'competition_id' 
                    # si es que df_h2h no está vacio
                    if not df_h2h.empty and 'competition_id' in df_h2h.columns:
                        comp_id = df_h2h.iloc[0]['competition_id']
                        
                    insert_satellite_stats(session, comp_id, stat_raw)
                    
                    # FASE 3.5: PLAYER PROPS FÚTBOL
                    if comp_id in [7, 11, 17, 25, 67, 229]:
                        df_futbol = client.get_soccer_player_stats(game_id)
                        if not df_futbol.empty:
                            resolver = EntityResolver(session)
                            for index, row in df_futbol.iterrows():
                                
                                p_name = row.get('nombre_jugador', 'Desconocido')
                                
                                # Validación de integridad: control de nulos en resolución de entidades
                                if p_name == 'Desconocido':
                                    continue
                                    
                                t_name = str(row.get('team_name', 'Equipo'))
                                
                                id_equipo_interno = resolver.resolve_team(name=t_name)
                                if id_equipo_interno == -1: 
                                    continue
                                    
                                id_jugador_interno = resolver.resolve_player(name=p_name, team_id=id_equipo_interno)
                                if id_jugador_interno == -1:
                                    continue
                                    
                                player_stat_fut = PlayerStatsFutbol(
                                    id_partido=game_id,
                                    id_jugador=id_jugador_interno,
                                    minutos=int(row.get('minutos', 0)),
                                    goles=int(row.get('goles', 0)),
                                    asistencias=int(row.get('asistencias', 0)),
                                    tiros_totales=int(row.get('tiros_totales', 0)),
                                    tiros_puerta=int(row.get('tiros_puerta', 0)),
                                    pases_precisos=int(row.get('pases_precisos', 0)),
                                    faltas_cometidas=int(row.get('faltas_cometidas', 0)),
                                    amarillas=int(row.get('amarillas', 0)),
                                    rojas=int(row.get('rojas', 0))
                                )
                                session.merge(player_stat_fut)
                                
                            logger.info(f"Sincronización DB completada: métricas de jugador (fútbol) procesadas en partido {game_id}.")

                    # Cierre Transaccional Atómico
                    session.commit()
                    logger.info(f"COMMIT Exitoso en PostgreSQL para el Partido {game_id}")
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Rollback ejecutado para el partido {game_id} por quiebre de integridad: {e}")

        # ==========================================
        # PASO A: EXTRAER DATAFRAME DE NBA_CLIENT
        # ==========================================
        logger.info(f"--- FASE 4: INICIO DE EXTRACCIÓN Y MAPEO: PLAYER PROPS NBA - {target_date} ---")
        df_nba = client_nba.get_player_props_by_date(target_date)
        
        if not df_nba.empty:
            with Session(engine) as session:
                # PASO B: Instanciar Middleware
                resolver = EntityResolver(session)
                try:
                    for index, row in df_nba.iterrows():
                        player_name = row.get('PLAYER_NAME', 'Desconocido')
                        
                        # Validación de nulos
                        minutos_crudos = row.get('MIN', 0)
                        min_jug = int(float(minutos_crudos)) if pd.notnull(minutos_crudos) else 0
                        pts_jug = int(row.get('PTS', 0))
                        if min_jug == 0 and pts_jug == 0:
                            continue
                            
                        # 1. Resolver ID Equipo Interno
                        team_raw_name = str(row.get('TEAM_NAME', 'NBA Team')) 
                        id_equipo_interno = resolver.resolve_team(name=team_raw_name)
                        
                        if id_equipo_interno == -1:
                            logger.warning(f"Omitido '{player_name}': Fallo en la resolución de identidad (Entity Resolution) para el cluster de nodos: '{team_raw_name}'.")
                            continue
                            
                        # 2. Resolver ID Partido Interno 
                        matchup_str = str(row.get('MATCHUP', ''))
                        if ' @ ' in matchup_str:
                            rival_name = matchup_str.split(' @ ')[1]
                        elif ' vs. ' in matchup_str:
                            rival_name = matchup_str.split(' vs. ')[1]
                        else:
                            rival_name = 'Rival Desconocido'
                            
                        id_equipo_visitante = resolver.resolve_team(name=rival_name)
                        if id_equipo_visitante == -1:
                            id_equipo_visitante = -1
                            
                        match_id_interno = resolver.resolve_match(
                            internal_home_id=id_equipo_interno, 
                            internal_away_id=id_equipo_visitante, 
                            date_str=target_date
                        )
                        
                        # 3. Resolver ID Jugador Interno (Creación Dinámica Si No Existe)
                        id_jugador_interno = resolver.resolve_player(name=player_name, team_id=id_equipo_interno)
                        
                        # Ignorar si falla la llave fundamental para evitar FK Constraint
                        if match_id_interno == -1 or id_jugador_interno == -1:
                            logger.warning(f"Omitido '{player_name}': Pérdida UUID (Match: {match_id_interno}, GenPlayer: {id_jugador_interno}).")
                            continue
                            
                        # PASO C: UPSERT DE TABLA PUENTE                        
                        player_stat = PlayerStatsNBA(
                            id_partido=match_id_interno,
                            id_jugador=id_jugador_interno,
                            minutos=min_jug,
                            puntos=int(row.get('PTS', 0)),
                            rebotes=int(row.get('REB', 0)),
                            asistencias=int(row.get('AST', 0)),
                            robos=int(row.get('STL', 0)),
                            bloqueos=int(row.get('BLK', 0)),
                            perdidas=int(row.get('TOV', 0)),
                            triples=int(row.get('FG3M', 0))
                        )
                        session.merge(player_stat) # Evita duplicación si se procesa el evento y luego se vuelve a extraer
                        
                    session.commit()
                    logger.info(f"Sincronización DB completada: métricas de jugador (NBA) procesadas para fecha {target_date}.")
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Aborto de Ingesta Player Props NBA: {e}")

        # ==========================================
        # PASO E: EXTRAER DATAFRAME DE MLB_CLIENT
        # ==========================================
        logger.info(f"--- FASE 5: INICIO DE EXTRACCIÓN Y MAPEO: PLAYER PROPS MLB - {target_date} ---")
        df_mlb = client_mlb.get_player_props_by_date(target_date)
        
        if not df_mlb.empty:
            with Session(engine) as session:
                resolver = EntityResolver(session)
                try:
                    for index, row in df_mlb.iterrows():
                        player_name = row.get('nombre_jugador', 'Desconocido')
                        
                        # Validación de nulos
                        turnos = int(row.get('turnos_al_bate', 0))
                        if turnos == 0:
                            continue
                            
                        team_raw_name = str(row.get('team_name', 'MLB Team'))
                        id_equipo_interno = resolver.resolve_team(name=team_raw_name)
                        
                        if id_equipo_interno == -1:
                            continue
                            
                        rival_name = str(row.get('rival_name', 'Rival Desconocido'))
                        id_equipo_visitante = resolver.resolve_team(name=rival_name)
                        if id_equipo_visitante == -1:
                            id_equipo_visitante = -1
                            
                        match_id_interno = resolver.resolve_match(
                            internal_home_id=id_equipo_interno, 
                            internal_away_id=id_equipo_visitante, 
                            date_str=target_date
                        )
                        
                        id_jugador_interno = resolver.resolve_player(name=player_name, team_id=id_equipo_interno)
                        
                        if match_id_interno == -1 or id_jugador_interno == -1:
                            continue
                            
                        player_stat_mlb = PlayerStatsMLB(
                            id_partido=match_id_interno,
                            id_jugador=id_jugador_interno,
                            turnos_al_bate=int(row.get('turnos_al_bate', 0)),
                            hits=int(row.get('hits', 0)),
                            carreras=int(row.get('carreras', 0)),
                            home_runs=int(row.get('home_runs', 0)),
                            carreras_impulsadas=int(row.get('carreras_impulsadas', 0)),
                            bases_por_bolas=int(row.get('bases_por_bolas', 0)),
                            ponches=int(row.get('ponches', 0))
                        )
                        session.merge(player_stat_mlb)
                        
                    session.commit()
                    logger.info(f"Sincronización DB completada: métricas de jugador (MLB) procesadas para fecha {target_date}.")
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Aborto de Ingesta Player Props MLB: {e}")

    # ==========================================
    # FASE 6: INGESTA DE FBREF (ESTADÍSTICAS AVANZADAS POR TEMPORADA)
    # ==========================================
    logger.info("--- FASE 6: INICIO DE EXTRACCIÓN GLOBAL FBREF ---")
    try:
        # Extraer equipos
        df_fbref_teams = client_fbref.get_advanced_team_stats(stat_type='shooting')
        if not df_fbref_teams.empty:
            df_fbref_teams.to_sql('fbref_team_stats', engine, if_exists='replace', index=False)
            logger.info(f"FBREF: Volcados {len(df_fbref_teams)} registros a la tabla 'fbref_team_stats'")
        else:
            logger.warning("FBREF: df_fbref_teams vacío. No se volcó información.")

        # Extraer jugadores (estadísticas estándar)
        df_fbref_players = client_fbref.get_advanced_player_stats(stat_type='standard')
        if not df_fbref_players.empty:
            df_fbref_players.to_sql('fbref_player_stats', engine, if_exists='replace', index=False)
            logger.info(f"FBREF: Volcados {len(df_fbref_players)} registros a la tabla 'fbref_player_stats'")
        else:
            logger.warning("FBREF: df_fbref_players vacío. No se volcó información.")

        # Extraer jugadores (estadísticas de tiro: xG, Tiros a Puerta)
        df_fbref_shooting = client_fbref.get_advanced_player_stats(stat_type='shooting')
        if not df_fbref_shooting.empty:
            df_fbref_shooting.to_sql('fbref_shooting_stats', engine, if_exists='replace', index=False)
            logger.info(f"FBREF: Volcados {len(df_fbref_shooting)} registros de tiro a la tabla 'fbref_shooting_stats'")
        else:
            logger.warning("FBREF: df_fbref_shooting vacío. No se volcaron estadísticas ofensivas avanzadas (xG/Tiros).")

    except Exception as e:
        logger.error(f"Error crítico en la Fase 6 (Ingesta FBRef): {e}")

    # TAREAS PENDIENTES DE ORQUESTACION
    # TODO: Activar async "odds_scraper" para extraer cuotas asociadas al ID Partido y guardar estado en tablas de cuotas Quant.

if __name__ == "__main__":
    logger.info(">>> ARRANQUE DE DATA WAREHOUSE PIPELINE <<<")
    # Para entornos Windows corremos el motor asíncrono
    asyncio.run(run_ingestion())
