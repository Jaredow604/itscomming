import logging
from datetime import timedelta, datetime
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, cast, Date
from rapidfuzz import process

# Modelos internos ORM
from src.data.models import Team, Player, Match

logger = logging.getLogger("EntityResolver")

class EntityResolver:
    """
    Middleware de Resolución de Entidades (Entity Resolution).
    Encargado de unificar nomenclaturas dispares provenientes de múltiples APIs 
    hacia los identificadores maestros de la base de datos PostgreSQL utilizando Fuzzy String Matching.
    """
    
    def __init__(self, session: Session):
        self.session = session
        
        # Caché en memoria para mitigar llamados I/O redundantes a PostgreSQL
        self._team_cache = {}
        self._player_cache = {}

    def resolve_team(self, name: str, sport_id: int = None) -> int:
        """
        Mapeo de Nomenclaturas de Equipos.
        Utiliza distancia Levenshtein contra los registros SQL si la búsqueda exacta fracasa.
        """
        # Búsqueda en caché local
        if name in self._team_cache:
            return self._team_cache[name]

        # Búsqueda exacta de subcadenas (SQL ILIKE)
        stmt = select(Team).where(Team.nombre.ilike(f"%{name}%"))
        exact_team = self.session.execute(stmt).scalars().first()
        
        if exact_team:
            self._team_cache[name] = exact_team.id_equipo
            return exact_team.id_equipo
            
        # Búsqueda difusa (rapidfuzz) en caso de fallos exactos
        logger.debug(f"Iniciando coincidencia difusa para el equipo: '{name}'")
        all_teams = self.session.execute(select(Team)).scalars().all()
        
        if not all_teams:
            raise ValueError("Infracción: No existen equipos registrados en la BD local. Requerido ejecutar ingesta primaria.")
            
        team_dict = {t.id_equipo: t.nombre for t in all_teams}
        
        # Retorna tupla: (StringCoincidencia, Score%, Key)
        best_match = process.extractOne(name, team_dict)
        
        # Límite Mínimo de Confianza = 90%
        if best_match and best_match[1] >= 90: 
            matched_id = best_match[2]
            logger.info(f"Coincidencia asimilada: '{name}' -> '{best_match[0]}' (Score: {best_match[1]}%)")
            self._team_cache[name] = matched_id
            return matched_id
            
        logger.warning(f"Entidad no relacionada encontrada ('{name}' score: {best_match[1] if best_match else 0}%). Registrando nuevo equipo en BD.")
        
        # Generación de ID Seguro
        max_team_id = self.session.execute(select(func.max(Team.id_equipo))).scalar()
        nuevo_id = (max_team_id + 1) if max_team_id is not None else 50000 
        
        if nuevo_id < 50000:
            nuevo_id = 50000
            
        nuevo_equipo = Team(id_equipo=nuevo_id, nombre=name)
        self.session.add(nuevo_equipo)
        self.session.flush()
        
        self._team_cache[name] = nuevo_id
        return nuevo_id

    def resolve_player(self, name: str, team_id: int = None) -> int:
        """
        Resolución de Identidad de Jugadores.
        Valida conflictos de homónimos triangulando contra team_id.
        """
        cache_key = f"{name}_{team_id}" if team_id else name
        if cache_key in self._player_cache:
            return self._player_cache[cache_key]
            
        # Extracción relacional SQL
        stmt = select(Player).where(Player.nombre.ilike(f"{name}%"))
        if team_id and team_id > 0:
            stmt = stmt.where(Player.id_equipo == team_id)
            
        matched_player = self.session.execute(stmt).scalars().first()
        
        if matched_player:
            self._player_cache[cache_key] = matched_player.id_jugador
            return matched_player.id_jugador
            
        # Inserción de entidad foránea (Fallback)
        logger.debug(f"Registrando nuevo jugador en BD: {name}")
        
        # Inserción asimétrica forzando index base fuera del rango auto-incremental de 365Scores para prevenir colisión
        max_id = self.session.execute(select(func.max(Player.id_jugador))).scalar()
        nuevo_id = (max_id + 1) if max_id is not None else 10000000 
        if nuevo_id < 10000000:
            nuevo_id = 10000000
            
        # Validación de Integridad Referencial (FK id_equipo)
        safe_team_id = team_id if team_id and team_id > 0 else 0
        if safe_team_id == 0:
            agente_libre = self.session.execute(select(Team).where(Team.id_equipo == 0)).scalars().first()
            if not agente_libre:
                self.session.add(Team(id_equipo=0, nombre="Agencia Libre"))
                self.session.flush()

        # Operación DML
        nuevo_jugador = Player(
            id_jugador=nuevo_id,
            id_equipo=safe_team_id,
            nombre=name
        )
        
        self.session.add(nuevo_jugador)
        self.session.flush() # Sincroniza estado para obtener PK pero mantiene transaccionalidad abierta

        
        self._player_cache[cache_key] = nuevo_id
        return nuevo_id

    def resolve_match(self, internal_home_id: int, internal_away_id: int, date_str: str) -> int:
        """
        Resolución de Partidos (Entity Relational Bridge).
        Tolerancia de fechas cruzando husos horarios (+/- 1 día de offset) para vincular competiciones originarias.
        """
        try:
            target_date = datetime.strptime(date_str, "%d/%m/%Y").date()
        except Exception as e:
            logger.error(f"Error parseando date_str {date_str}: {e}")
            return -1
            
        # Ventana de toleramiento de husos horarios
        start_margin = target_date - timedelta(days=1)
        end_margin = target_date + timedelta(days=1)
        
        stmt = select(Match).where(
            and_(
                or_(
                    and_(Match.id_local == internal_home_id, Match.id_visitante == internal_away_id),
                    and_(Match.id_local == internal_away_id, Match.id_visitante == internal_home_id)
                ),
                cast(Match.fecha, Date) >= start_margin,
                cast(Match.fecha, Date) <= end_margin
            )
        )
        
        match_obj = self.session.execute(stmt).scalars().first()
        
        if match_obj:
            return match_obj.id_partido
            
        logger.warning(f"Partido referencial no encontrado (Eq_Local {internal_home_id} vs Eq_Visit {internal_away_id}) fecha ~{target_date}. Insertando entidad nueva.")
        
        # Generación de ID Seguro para Partido Foráneo
        max_match_id = self.session.execute(select(func.max(Match.id_partido))).scalar()
        nuevo_id_partido = (max_match_id + 1) if max_match_id is not None else 9000000
        
        nuevo_partido = Match(
            id_partido=nuevo_id_partido,
            id_local=internal_home_id,
            id_visitante=internal_away_id,
            fecha=target_date,
            fstatus="Terminado"
        )
        
        self.session.add(nuevo_partido)
        self.session.flush()
        
        return nuevo_id_partido
