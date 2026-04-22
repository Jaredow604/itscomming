from datetime import datetime
from typing import List, Optional
from sqlalchemy import ForeignKey, Numeric, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ==========================================
# CLASE BASE DE SQLALCHEMY 2.0
# ==========================================
class Base(DeclarativeBase):
    """
    Clase base declarativa en SQLAlchemy 2.0. 
    Todos los modelos heredarán de esta para el mapeo hacia PostgreSQL.
    """
    pass

# ==========================================
# DEFINICIÓN DE MODELOS (TABLAS)
# ==========================================

class Team(Base):
    __tablename__ = 'equipos'

    # ID extraído directo desde la API de 365Scores (autoincrement=False)
    id_equipo: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Métricas y Promedios Críticos (Numeric 5,2 ideal para floats monetarios o xG)
    prom_corners: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    prom_tiros_puerta: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    prom_goles: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Relaciones (Bidireccionales)
    jugadores: Mapped[List["Player"]] = relationship(
        back_populates="equipo", 
        cascade="all, delete-orphan" # Si un equipo desaparece, eliminamos sus jugadores
    )
    tabla: Mapped[Optional["LeagueTable"]] = relationship(
        back_populates="equipo",
        cascade="all, delete-orphan"
    )


class Player(Base):
    __tablename__ = 'jugadores'

    # PK primaria usual
    id_jugador: Mapped[int] = mapped_column(primary_key=True, autoincrement=False) # También heredable de la API si se desea
    
    # Llave foránea hacia 'equipos'
    id_equipo: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Desempeño Estadístico
    goles: Mapped[int] = mapped_column(Integer, default=0)
    asistencias: Mapped[int] = mapped_column(Integer, default=0)
    tar_amarilla: Mapped[int] = mapped_column(Integer, default=0)
    prom_faltas: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Relación de vuelta al equipo (permite hacer: jugador.equipo.nombre)
    equipo: Mapped["Team"] = relationship(back_populates="jugadores")
    
    # Relación: Player Props (Uno a Muchos a Tablas Puente)
    stats_nba: Mapped[List["PlayerStatsNBA"]] = relationship(back_populates="jugador", cascade="all, delete-orphan")
    stats_mlb: Mapped[List["PlayerStatsMLB"]] = relationship(back_populates="jugador", cascade="all, delete-orphan")
    stats_futbol: Mapped[List["PlayerStatsFutbol"]] = relationship(back_populates="jugador", cascade="all, delete-orphan")


class Match(Base):
    __tablename__ = 'partidos'

    # Game ID de 365Scores
    id_partido: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    
    # Doble Foreign Key hacia la misma tabla (equipos)
    id_local: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    id_visitante: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    
    # Fechas y estatus del partido
    fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fstatus: Mapped[str] = mapped_column(String(50)) # Ej: "Ended", "Postponed", "Fixture"

    # Relaciones específicas debido a la doble FK
    # Permite hacer cosas como: partido.local.prom_goles o partido.visitante.nombre
    local: Mapped["Team"] = relationship(foreign_keys=[id_local])
    visitante: Mapped["Team"] = relationship(foreign_keys=[id_visitante])
    
    # Relaciones 1:1 Satélite ("Core + Extensión")
    stats_nba: Mapped[Optional["MatchStatsNBA"]] = relationship(back_populates="partido", cascade="all, delete-orphan")
    stats_mlb: Mapped[Optional["MatchStatsMLB"]] = relationship(back_populates="partido", cascade="all, delete-orphan")
    stats_futbol: Mapped[Optional["MatchStatsFutbol"]] = relationship(back_populates="partido", cascade="all, delete-orphan")
    
    # Relaciones 1:N Bridge (Player Props)
    jugadores_nba: Mapped[List["PlayerStatsNBA"]] = relationship(back_populates="partido", cascade="all, delete-orphan")
    jugadores_mlb: Mapped[List["PlayerStatsMLB"]] = relationship(back_populates="partido", cascade="all, delete-orphan")
    jugadores_futbol: Mapped[List["PlayerStatsFutbol"]] = relationship(back_populates="partido", cascade="all, delete-orphan")

# ==========================================
# SUPER-TABLAS SATÉLITE DE DEPORTES EXACTOS
# ==========================================

class MatchStatsNBA(Base):
    __tablename__ = 'stats_nba'

    # Actúa como Primary Key y Foreign Key bidireccional
    id_partido: Mapped[int] = mapped_column(ForeignKey("partidos.id_partido"), primary_key=True)
    
    # Métricas
    puntos_local: Mapped[int] = mapped_column(Integer, default=0)
    puntos_visitante: Mapped[int] = mapped_column(Integer, default=0)
    rebotes_local: Mapped[int] = mapped_column(Integer, default=0)
    rebotes_visitante: Mapped[int] = mapped_column(Integer, default=0)
    triples_local: Mapped[int] = mapped_column(Integer, default=0)
    triples_visitante: Mapped[int] = mapped_column(Integer, default=0)

    # Relación Inversa al Partido
    partido: Mapped["Match"] = relationship(back_populates="stats_nba")

class MatchStatsMLB(Base):
    __tablename__ = 'stats_mlb'

    id_partido: Mapped[int] = mapped_column(ForeignKey("partidos.id_partido"), primary_key=True)
    
    # Métricas
    carreras_local: Mapped[int] = mapped_column(Integer, default=0)
    carreras_visitante: Mapped[int] = mapped_column(Integer, default=0)
    hits_local: Mapped[int] = mapped_column(Integer, default=0)
    hits_visitante: Mapped[int] = mapped_column(Integer, default=0)
    errores_local: Mapped[int] = mapped_column(Integer, default=0)
    errores_visitante: Mapped[int] = mapped_column(Integer, default=0)

    # Relación Inversa al Partido
    partido: Mapped["Match"] = relationship(back_populates="stats_mlb")

class MatchStatsFutbol(Base):
    __tablename__ = 'stats_futbol'

    # Actúa como Primary Key y Foreign Key bidireccional
    id_partido: Mapped[int] = mapped_column(ForeignKey("partidos.id_partido"), primary_key=True)
    
    # Métricas de Partido Enteras
    goles_local: Mapped[int] = mapped_column(Integer, default=0)
    goles_visitante: Mapped[int] = mapped_column(Integer, default=0)
    posesion_local: Mapped[int] = mapped_column(Integer, default=0)
    posesion_visitante: Mapped[int] = mapped_column(Integer, default=0)
    tiros_puerta_local: Mapped[int] = mapped_column(Integer, default=0)
    tiros_puerta_visitante: Mapped[int] = mapped_column(Integer, default=0)
    corners_local: Mapped[int] = mapped_column(Integer, default=0)
    corners_visitante: Mapped[int] = mapped_column(Integer, default=0)
    amarillas_local: Mapped[int] = mapped_column(Integer, default=0)
    amarillas_visitante: Mapped[int] = mapped_column(Integer, default=0)
    rojas_local: Mapped[int] = mapped_column(Integer, default=0)
    rojas_visitante: Mapped[int] = mapped_column(Integer, default=0)

    # Métricas Decimales Avanzadas (Machine Learning Focus)
    xg_local: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    xg_visitante: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Relación Inversa al Partido
    partido: Mapped["Match"] = relationship(back_populates="stats_futbol")

# ==========================================
# TABLAS PUENTE PARA PLAYER PROPS
# ==========================================

class PlayerStatsNBA(Base):
    __tablename__ = 'stats_jugador_nba'

    id_partido: Mapped[int] = mapped_column(ForeignKey("partidos.id_partido"), primary_key=True)
    id_jugador: Mapped[int] = mapped_column(ForeignKey("jugadores.id_jugador"), primary_key=True)

    # Métricas Específicas Player Props NBA
    minutos: Mapped[int] = mapped_column(Integer, default=0)
    puntos: Mapped[int] = mapped_column(Integer, default=0)
    rebotes: Mapped[int] = mapped_column(Integer, default=0)
    asistencias: Mapped[int] = mapped_column(Integer, default=0)
    robos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueos: Mapped[int] = mapped_column(Integer, default=0)
    perdidas: Mapped[int] = mapped_column(Integer, default=0)
    triples: Mapped[int] = mapped_column(Integer, default=0)

    # Relaciones Inversas (Uno a Muchos a Tablas Core)
    partido: Mapped["Match"] = relationship(back_populates="jugadores_nba")
    jugador: Mapped["Player"] = relationship(back_populates="stats_nba")

class PlayerStatsMLB(Base):
    __tablename__ = 'stats_jugador_mlb'

    id_partido: Mapped[int] = mapped_column(ForeignKey("partidos.id_partido"), primary_key=True)
    id_jugador: Mapped[int] = mapped_column(ForeignKey("jugadores.id_jugador"), primary_key=True)

    # Métricas Específicas Player Props MLB
    turnos_al_bate: Mapped[int] = mapped_column(Integer, default=0)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    carreras: Mapped[int] = mapped_column(Integer, default=0)
    home_runs: Mapped[int] = mapped_column(Integer, default=0)
    carreras_impulsadas: Mapped[int] = mapped_column(Integer, default=0)
    bases_por_bolas: Mapped[int] = mapped_column(Integer, default=0)
    ponches: Mapped[int] = mapped_column(Integer, default=0)

    # Relaciones Inversas (Uno a Muchos a Tablas Core)
    partido: Mapped["Match"] = relationship(back_populates="jugadores_mlb")
    jugador: Mapped["Player"] = relationship(back_populates="stats_mlb")


class PlayerStatsFutbol(Base):
    __tablename__ = 'stats_jugador_futbol'

    id_partido: Mapped[int] = mapped_column(ForeignKey("partidos.id_partido"), primary_key=True)
    id_jugador: Mapped[int] = mapped_column(ForeignKey("jugadores.id_jugador"), primary_key=True)

    minutos: Mapped[int] = mapped_column(Integer, default=0)
    goles: Mapped[int] = mapped_column(Integer, default=0)
    asistencias: Mapped[int] = mapped_column(Integer, default=0)
    tiros_totales: Mapped[int] = mapped_column(Integer, default=0)
    tiros_puerta: Mapped[int] = mapped_column(Integer, default=0)
    pases_precisos: Mapped[int] = mapped_column(Integer, default=0)
    faltas_cometidas: Mapped[int] = mapped_column(Integer, default=0)
    amarillas: Mapped[int] = mapped_column(Integer, default=0)
    rojas: Mapped[int] = mapped_column(Integer, default=0)

    # Relaciones Inversas (Uno a Muchos a Tablas Core)
    partido: Mapped["Match"] = relationship(back_populates="jugadores_futbol")
    jugador: Mapped["Player"] = relationship(back_populates="stats_futbol")

class LeagueTable(Base):
    __tablename__ = 'tabla_general'

    id_tabla: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_equipo: Mapped[int] = mapped_column(ForeignKey("equipos.id_equipo"))
    
    # Estadísticas Globales del Torneo
    puntos: Mapped[int] = mapped_column(Integer, default=0)
    dif_goles: Mapped[int] = mapped_column(Integer, default=0)
    partidos_jugados: Mapped[int] = mapped_column(Integer, default=0)

    # Relación directa al equipo
    equipo: Mapped["Team"] = relationship(back_populates="tabla")


# ==========================================
# PRUEBA Y CREACIÓN DE ESQUEMAS DDL
# ==========================================
if __name__ == '__main__':
    # Creamos un motor temporal en memoria (SQLite) solo para validar que el DDL está perfecto.
    # En producción simplemente cambias este string por tu cadena de PostgreSQL:
    engine = create_engine("postgresql+psycopg2://postgres:Jk9oe@localhost:5432/itscoming_db")
    

    
    # Emite los comandos CREATE TABLE correspondientes en la consola
    print("--- INICIANDO CONSTRUCCIÓN DE MODELOS EN EL MOTOR ORM ---")
    Base.metadata.create_all(bind=engine)
    print("--- ESQUEMAS CONSTRUIDOS CORRECTAMENTE ---")
