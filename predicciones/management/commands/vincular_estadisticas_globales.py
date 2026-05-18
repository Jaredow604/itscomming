import logging
from django.core.management.base import BaseCommand
from rapidfuzz import fuzz, process
from sqlalchemy import update
from database import SessionLocal
from src.data.models import (
    Team, Player, Match, 
    FBrefTeamStats, FBrefPlayerStats, NBAPlayerHistory, 
    NBAPlayerStatsClean, MLMatchFeatures, MatchHistoryStats
)
from predicciones.entity_resolver import clean_team_name

logger = logging.getLogger('vincular_estadisticas')

# Configuración del logger si no existe handler
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

class Command(BaseCommand):
    help = 'Vincula las tablas crudas de estadísticas globales hacia los modelos Core en PostgreSQL.'

    def handle(self, *args, **kwargs):
        session = SessionLocal()
        
        try:
            self.stdout.write(self.style.SUCCESS('Iniciando vinculación de estadísticas globales (SQLAlchemy)...'))
            
            # 1. Cargar diccionarios en memoria (Core Models) para acceso O(1) y Fuzzy Match
            self.stdout.write('Cargando diccionarios Core en memoria...')
            equipos_db = session.query(Team).all()
            jugadores_db = session.query(Player).all()
            
            # { "nombre_limpio": id_equipo }
            equipos_clean_dict = {clean_team_name(e.nombre): e.id_equipo for e in equipos_db if e.nombre}
            # { "nombre_exacto_lower": id_jugador }
            jugadores_exact_dict = {j.nombre.lower(): j.id_jugador for j in jugadores_db if j.nombre}
            
            self.stdout.write(f'Cargados {len(equipos_clean_dict)} equipos y {len(jugadores_exact_dict)} jugadores.')
            
            self.procesar_fbref_team_stats(session, equipos_clean_dict)
            self.procesar_fbref_player_stats(session, equipos_clean_dict, jugadores_exact_dict)
            self.procesar_nba_player_history(session, equipos_clean_dict, jugadores_exact_dict)
            self.procesar_nba_player_stats_clean(session, equipos_clean_dict, jugadores_exact_dict)
            self.procesar_ml_match_features(session, equipos_clean_dict)
            self.procesar_match_history_stats(session, equipos_clean_dict)
            
            self.stdout.write(self.style.SUCCESS('Proceso masivo finalizado con éxito.'))
            
        except Exception as e:
            logger.error(f"Error fatal en el script: {e}")
            session.rollback()
        finally:
            session.close()

    def procesar_fbref_team_stats(self, session, equipos_clean_dict):
        self.stdout.write('--- Procesando FBrefTeamStats ---')
        updates = []
        huerfanos = set()
        query = session.query(FBrefTeamStats).filter(FBrefTeamStats.equipo_fk == None).yield_per(1000)
        choices = {id_eq: nombre_limpio for nombre_limpio, id_eq in equipos_clean_dict.items()}
        
        for row in query:
            if not row.team: continue
            match = process.extractOne(clean_team_name(row.team), choices, scorer=fuzz.token_sort_ratio, score_cutoff=80)
            if match:
                updates.append({'id': row.id, 'equipo_fk': match[2]})
            else:
                huerfanos.add(row.team)
                
        if updates:
            session.bulk_update_mappings(FBrefTeamStats, updates)
            session.commit()
            self.stdout.write(self.style.SUCCESS(f'Actualizados {len(updates)} registros en FBrefTeamStats.'))
        if huerfanos:
            logger.warning(f"Huérfanos FBrefTeamStats ({len(huerfanos)} únicos): {list(huerfanos)[:10]}...")

    def procesar_fbref_player_stats(self, session, equipos_clean_dict, jugadores_exact_dict):
        self.stdout.write('--- Procesando FBrefPlayerStats ---')
        updates = []
        huerfanos_eq, huerfanos_jug = set(), set()
        query = session.query(FBrefPlayerStats).filter((FBrefPlayerStats.equipo_fk == None) | (FBrefPlayerStats.jugador_fk == None)).yield_per(2000)
        choices_eq = {id_eq: nm for nm, id_eq in equipos_clean_dict.items()}
        
        for row in query:
            update_dict = {'id': row.id}
            modified = False
            if not row.equipo_fk and row.team:
                match = process.extractOne(clean_team_name(row.team), choices_eq, scorer=fuzz.token_sort_ratio, score_cutoff=80)
                if match:
                    update_dict['equipo_fk'] = match[2]
                    modified = True
                else:
                    huerfanos_eq.add(row.team)
            if not row.jugador_fk and row.player:
                p_lower = row.player.lower()
                if p_lower in jugadores_exact_dict:
                    update_dict['jugador_fk'] = jugadores_exact_dict[p_lower]
                    modified = True
                else:
                    huerfanos_jug.add(row.player)
            if modified: updates.append(update_dict)
            
        if updates:
            session.bulk_update_mappings(FBrefPlayerStats, updates)
            session.commit()
            self.stdout.write(self.style.SUCCESS(f'Actualizados {len(updates)} registros en FBrefPlayerStats.'))
        if huerfanos_eq: logger.warning(f"Huérfanos Eq FBrefPlayer ({len(huerfanos_eq)} únicos): {list(huerfanos_eq)[:10]}...")
        if huerfanos_jug: logger.warning(f"Huérfanos Jug FBrefPlayer ({len(huerfanos_jug)} únicos): {list(huerfanos_jug)[:10]}...")

    def procesar_nba_player_history(self, session, equipos_clean_dict, jugadores_exact_dict):
        self.stdout.write('--- Procesando NBAPlayerHistory ---')
        updates = []
        huerfanos_eq, huerfanos_jug = set(), set()
        query = session.query(NBAPlayerHistory).filter((NBAPlayerHistory.equipo_fk == None) | (NBAPlayerHistory.jugador_fk == None)).yield_per(2000)
        choices_eq = {id_eq: nm for nm, id_eq in equipos_clean_dict.items()}
        
        for row in query:
            update_dict = {'id': row.id}
            modified = False
            if not row.equipo_fk and row.team_name:
                match = process.extractOne(clean_team_name(row.team_name), choices_eq, scorer=fuzz.token_sort_ratio, score_cutoff=85)
                if match:
                    update_dict['equipo_fk'] = match[2]
                    modified = True
                else:
                    huerfanos_eq.add(row.team_name)
            if not row.jugador_fk and row.player_name:
                p_lower = row.player_name.lower()
                if p_lower in jugadores_exact_dict:
                    update_dict['jugador_fk'] = jugadores_exact_dict[p_lower]
                    modified = True
                else:
                    huerfanos_jug.add(row.player_name)
            if modified: updates.append(update_dict)
            
        if updates:
            session.bulk_update_mappings(NBAPlayerHistory, updates)
            session.commit()
            self.stdout.write(self.style.SUCCESS(f'Actualizados {len(updates)} registros en NBAPlayerHistory.'))

    def procesar_nba_player_stats_clean(self, session, equipos_clean_dict, jugadores_exact_dict):
        self.stdout.write('--- Procesando NBAPlayerStatsClean ---')
        updates = []
        query = session.query(NBAPlayerStatsClean).filter((NBAPlayerStatsClean.equipo_fk == None) | (NBAPlayerStatsClean.jugador_fk == None)).yield_per(2000)
        choices_eq = {id_eq: nm for nm, id_eq in equipos_clean_dict.items()}
        for row in query:
            update_dict = {'id': row.id}
            modified = False
            if not row.equipo_fk and row.team_name:
                match = process.extractOne(clean_team_name(row.team_name), choices_eq, scorer=fuzz.token_sort_ratio, score_cutoff=85)
                if match:
                    update_dict['equipo_fk'] = match[2]
                    modified = True
            if not row.jugador_fk and row.player_name:
                p_lower = row.player_name.lower()
                if p_lower in jugadores_exact_dict:
                    update_dict['jugador_fk'] = jugadores_exact_dict[p_lower]
                    modified = True
            if modified: updates.append(update_dict)
        if updates:
            session.bulk_update_mappings(NBAPlayerStatsClean, updates)
            session.commit()
            self.stdout.write(self.style.SUCCESS(f'Actualizados {len(updates)} registros en NBAPlayerStatsClean.'))

    def procesar_ml_match_features(self, session, equipos_clean_dict):
        self.stdout.write('--- Procesando MLMatchFeatures ---')
        updates = []
        query = session.query(MLMatchFeatures).filter(MLMatchFeatures.equipo_fk == None).yield_per(2000)
        choices_eq = {id_eq: nm for nm, id_eq in equipos_clean_dict.items()}
        for row in query:
            if not row.team: continue
            match = process.extractOne(clean_team_name(row.team), choices_eq, scorer=fuzz.token_sort_ratio, score_cutoff=85)
            if match: updates.append({'id': row.id, 'equipo_fk': match[2]})
        if updates:
            session.bulk_update_mappings(MLMatchFeatures, updates)
            session.commit()
            self.stdout.write(self.style.SUCCESS(f'Actualizados {len(updates)} registros en MLMatchFeatures.'))

    def procesar_match_history_stats(self, session, equipos_clean_dict):
        self.stdout.write('--- Procesando MatchHistoryStats ---')
        updates = []
        query = session.query(MatchHistoryStats).filter((MatchHistoryStats.local_fk == None) | (MatchHistoryStats.visitante_fk == None)).yield_per(2000)
        choices_eq = {id_eq: nm for nm, id_eq in equipos_clean_dict.items()}
        for row in query:
            update_dict = {'id': row.id}
            modified = False
            if not row.local_fk and row.home_team:
                match = process.extractOne(clean_team_name(row.home_team), choices_eq, scorer=fuzz.token_sort_ratio, score_cutoff=85)
                if match:
                    update_dict['local_fk'] = match[2]
                    modified = True
            if not row.visitante_fk and row.away_team:
                match = process.extractOne(clean_team_name(row.away_team), choices_eq, scorer=fuzz.token_sort_ratio, score_cutoff=85)
                if match:
                    update_dict['visitante_fk'] = match[2]
                    modified = True
            if modified: updates.append(update_dict)
        if updates:
            session.bulk_update_mappings(MatchHistoryStats, updates)
            session.commit()
            self.stdout.write(self.style.SUCCESS(f'Actualizados {len(updates)} registros en MatchHistoryStats.'))
