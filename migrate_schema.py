"""
migrate_schema.py — Sincroniza el schema de la BD existente con los nuevos modelos

Agrega columnas faltantes y tablas nuevas sin destruir datos existentes.

Uso:
    python migrate_schema.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from database import engine
from sqlalchemy import text


def get_existing_columns(table_name):
    """Obtiene las columnas existentes de una tabla."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :table
        """), {"table": table_name})
        return [row[0] for row in result.fetchall()]


def add_column_if_not_exists(table, column, col_type):
    """Agrega una columna si no existe."""
    cols = get_existing_columns(table)
    if column not in cols:
        print(f"  Agregando {column} a {table}...")
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            conn.commit()
        return True
    return False


def rename_column_if_exists(table, old_name, new_name):
    """Renombra una columna si old_name existe y new_name no."""
    cols = get_existing_columns(table)
    if old_name in cols and new_name not in cols:
        print(f"  Renombrando {old_name} -> {new_name} en {table}...")
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}"))
            conn.commit()
        return True
    return False


def table_exists(table_name):
    """Verifica si una tabla existe."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = :table
            )
        """), {"table": table_name})
        return result.scalar()


def create_table_if_not_exists(table_name, definition):
    """Crea una tabla si no existe."""
    if not table_exists(table_name):
        print(f"  Creando {table_name}...")
        with engine.connect() as conn:
            conn.execute(text(definition))
            conn.commit()
        return True
    return False


def migrate():
    """Ejecuta todas las migraciones de schema necesarias."""
    print("=" * 60)
    print(" MIGRACION DE SCHEMA — It's Coming v3.0")
    print("=" * 60)

    # ── 1. Tabla equipos ──
    print("\n[1/7] Verificando tabla equipos...")
    add_column_if_not_exists('equipos', 'id_equipo', 'BIGINT')
    add_column_if_not_exists('equipos', 'logo_url', 'VARCHAR(500)')
    add_column_if_not_exists('equipos', 'prom_corners', 'NUMERIC(5,2) DEFAULT 0')
    add_column_if_not_exists('equipos', 'prom_tiros_puerta', 'NUMERIC(5,2) DEFAULT 0')
    add_column_if_not_exists('equipos', 'prom_goles', 'NUMERIC(5,2) DEFAULT 0')

    # Si id_equipo se acaba de crear, poblar con valores
    with engine.connect() as conn:
        null_check = conn.execute(text("SELECT COUNT(*) FROM equipos WHERE id_equipo IS NULL")).scalar()
        if null_check > 0:
            print("  Poblando id_equipo con valores...")
            conn.execute(text("""
                UPDATE equipos SET id_equipo = 100000 + id WHERE id_equipo IS NULL
            """))
            conn.commit()

        # Verificar PK
        pk_check = conn.execute(text("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'equipos' AND constraint_type = 'PRIMARY KEY'
        """)).fetchone()
        if not pk_check:
            print("  Agregando PK a id_equipo...")
            conn.execute(text("ALTER TABLE equipos ADD PRIMARY KEY (id_equipo)"))
            conn.commit()

    print("  OK Tabla equipos sincronizada.")

    # ── 2. Tabla partidos ──
    print("\n[2/7] Verificando tabla partidos...")
    add_column_if_not_exists('partidos', 'id_partido', 'BIGINT')
    add_column_if_not_exists('partidos', 'fstatus', "VARCHAR(50) DEFAULT 'Fixture'")
    add_column_if_not_exists('partidos', 'goles_local', 'INTEGER')
    add_column_if_not_exists('partidos', 'goles_visitante', 'INTEGER')
    add_column_if_not_exists('partidos', 'jugado', 'BOOLEAN DEFAULT false')

    rename_column_if_exists('partidos', 'local_id', 'id_local')
    rename_column_if_exists('partidos', 'visitante_id', 'id_visitante')

    with engine.connect() as conn:
        null_check = conn.execute(text("SELECT COUNT(*) FROM partidos WHERE id_partido IS NULL")).scalar()
        if null_check > 0:
            print("  Poblando id_partido con valores...")
            conn.execute(text("""
                UPDATE partidos SET id_partido = 1000000 + id WHERE id_partido IS NULL
            """))
            conn.commit()

        pk_check = conn.execute(text("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'partidos' AND constraint_type = 'PRIMARY KEY'
        """)).fetchone()
        if not pk_check:
            print("  Agregando PK a id_partido...")
            conn.execute(text("ALTER TABLE partidos ADD PRIMARY KEY (id_partido)"))
            conn.commit()

    print("  OK Tabla partidos sincronizada.")

    # ── 3. Tabla match_history_stats ──
    print("\n[3/7] Verificando tabla match_history_stats...")

    if not table_exists('match_history_stats'):
        print("  Creando match_history_stats...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE match_history_stats (
                    id SERIAL PRIMARY KEY,
                    league VARCHAR(100),
                    season VARCHAR(50),
                    date TIMESTAMP,
                    home_team VARCHAR(100),
                    away_team VARCHAR(100),
                    home_score INTEGER,
                    away_score INTEGER,
                    home_xg NUMERIC(5,2),
                    away_xg NUMERIC(5,2),
                    home_form_gf NUMERIC(5,2),
                    home_form_ga NUMERIC(5,2),
                    away_form_gf NUMERIC(5,2),
                    away_form_ga NUMERIC(5,2),
                    home_form_xgf NUMERIC(5,2),
                    home_form_xga NUMERIC(5,2),
                    away_form_xgf NUMERIC(5,2),
                    away_form_xga NUMERIC(5,2),
                    total_goals INTEGER,
                    result INTEGER,
                    local_fk BIGINT,
                    visitante_fk BIGINT,
                    partido_fk BIGINT
                )
            """))
            conn.commit()
    else:
        cols_to_add = [
            ('league', 'VARCHAR(100)'),
            ('season', 'VARCHAR(50)'),
            ('date', 'TIMESTAMP'),
            ('home_score', 'INTEGER'),
            ('away_score', 'INTEGER'),
            ('home_xg', 'NUMERIC(5,2)'),
            ('away_xg', 'NUMERIC(5,2)'),
            ('home_form_gf', 'NUMERIC(5,2)'),
            ('home_form_ga', 'NUMERIC(5,2)'),
            ('away_form_gf', 'NUMERIC(5,2)'),
            ('away_form_ga', 'NUMERIC(5,2)'),
            ('home_form_xgf', 'NUMERIC(5,2)'),
            ('home_form_xga', 'NUMERIC(5,2)'),
            ('away_form_xgf', 'NUMERIC(5,2)'),
            ('away_form_xga', 'NUMERIC(5,2)'),
            ('total_goals', 'INTEGER'),
            ('result', 'INTEGER'),
            ('local_fk', 'BIGINT'),
            ('visitante_fk', 'BIGINT'),
            ('partido_fk', 'BIGINT'),
        ]
        for col_name, col_type in cols_to_add:
            add_column_if_not_exists('match_history_stats', col_name, col_type)

    print("  OK Tabla match_history_stats sincronizada.")

    # ── 4. Tabla ml_match_features ──
    print("\n[4/7] Verificando tabla ml_match_features...")

    if not table_exists('ml_match_features'):
        print("  Creando ml_match_features...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE ml_match_features (
                    id SERIAL PRIMARY KEY,
                    league VARCHAR(100),
                    season VARCHAR(50),
                    date TIMESTAMP,
                    home_team VARCHAR(100),
                    away_team VARCHAR(100),
                    home_score INTEGER,
                    away_score INTEGER,
                    home_form_gf NUMERIC(5,2),
                    home_form_ga NUMERIC(5,2),
                    away_form_gf NUMERIC(5,2),
                    away_form_ga NUMERIC(5,2),
                    home_form_xgf NUMERIC(5,2),
                    home_form_xga NUMERIC(5,2),
                    away_form_xgf NUMERIC(5,2),
                    away_form_xga NUMERIC(5,2),
                    total_goals INTEGER,
                    result INTEGER,
                    equipo_fk BIGINT,
                    partido_fk BIGINT
                )
            """))
            conn.commit()
    else:
        cols_to_add = [
            ('league', 'VARCHAR(100)'),
            ('season', 'VARCHAR(50)'),
            ('date', 'TIMESTAMP'),
            ('home_score', 'INTEGER'),
            ('away_score', 'INTEGER'),
            ('home_form_gf', 'NUMERIC(5,2)'),
            ('home_form_ga', 'NUMERIC(5,2)'),
            ('away_form_gf', 'NUMERIC(5,2)'),
            ('away_form_ga', 'NUMERIC(5,2)'),
            ('home_form_xgf', 'NUMERIC(5,2)'),
            ('home_form_xga', 'NUMERIC(5,2)'),
            ('away_form_xgf', 'NUMERIC(5,2)'),
            ('away_form_xga', 'NUMERIC(5,2)'),
            ('total_goals', 'INTEGER'),
            ('result', 'INTEGER'),
        ]
        for col_name, col_type in cols_to_add:
            add_column_if_not_exists('ml_match_features', col_name, col_type)

    print("  OK Tabla ml_match_features sincronizada.")

    # ── 5. Tablas nuevas ──
    print("\n[5/7] Creando tablas nuevas...")

    create_table_if_not_exists('team_rolling_stats', """
        CREATE TABLE team_rolling_stats (
            id SERIAL PRIMARY KEY,
            id_equipo BIGINT REFERENCES equipos(id_equipo),
            fecha_calculo TIMESTAMP NOT NULL,
            ventana INTEGER DEFAULT 5,
            deporte VARCHAR(50) DEFAULT 'futbol',
            prom_goles_favor NUMERIC(5,2),
            prom_goles_contra NUMERIC(5,2),
            prom_xg_favor NUMERIC(5,2),
            prom_xg_contra NUMERIC(5,2)
        )
    """)

    create_table_if_not_exists('scaler_registry', """
        CREATE TABLE scaler_registry (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            ruta_archivo VARCHAR(500) NOT NULL,
            deporte VARCHAR(50) DEFAULT 'futbol',
            features_entrenadas VARCHAR(500),
            n_samples_entrenamiento INTEGER DEFAULT 0,
            fecha_entrenamiento TIMESTAMP DEFAULT NOW(),
            activo INTEGER DEFAULT 1
        )
    """)

    create_table_if_not_exists('alias_equipos', """
        CREATE TABLE IF NOT EXISTS alias_equipos (
            id SERIAL PRIMARY KEY,
            nombre_fuente VARCHAR(200) UNIQUE NOT NULL,
            id_equipo BIGINT REFERENCES equipos(id_equipo)
        )
    """)

    create_table_if_not_exists('dailyschedule', """
        CREATE TABLE IF NOT EXISTS dailyschedule (
            id SERIAL PRIMARY KEY,
            sport VARCHAR(50) NOT NULL,
            home_team VARCHAR(100) NOT NULL,
            away_team VARCHAR(100) NOT NULL,
            match_date DATE NOT NULL,
            start_time TIMESTAMP,
            equipo_local_fk BIGINT REFERENCES equipos(id_equipo),
            equipo_visitante_fk BIGINT REFERENCES equipos(id_equipo)
        )
    """)

    # Agregar columnas a dailyschedule si ya existe
    if table_exists('dailyschedule'):
        add_column_if_not_exists('dailyschedule', 'equipo_local_fk', 'BIGINT')
        add_column_if_not_exists('dailyschedule', 'equipo_visitante_fk', 'BIGINT')

    create_table_if_not_exists('ml_raw_player_data', """
        CREATE TABLE IF NOT EXISTS ml_raw_player_data (
            id SERIAL PRIMARY KEY,
            player_name VARCHAR(100) NOT NULL,
            team_name VARCHAR(100) NOT NULL,
            deporte VARCHAR(50) DEFAULT 'futbol',
            playing_time_min NUMERIC(10,2),
            total_shots NUMERIC(10,2),
            standard_sot NUMERIC(10,2),
            xg NUMERIC(10,2),
            pts NUMERIC(10,2),
            reb NUMERIC(10,2),
            ast NUMERIC(10,2),
            performance_gls NUMERIC(10,2),
            jugador_fk BIGINT,
            equipo_fk BIGINT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    if table_exists('ml_raw_player_data'):
        add_column_if_not_exists('ml_raw_player_data', 'deporte', "VARCHAR(50) DEFAULT 'futbol'")
        add_column_if_not_exists('ml_raw_player_data', 'xg', 'NUMERIC(10,2)')
        add_column_if_not_exists('ml_raw_player_data', 'pts', 'NUMERIC(10,2)')
        add_column_if_not_exists('ml_raw_player_data', 'reb', 'NUMERIC(10,2)')
        add_column_if_not_exists('ml_raw_player_data', 'ast', 'NUMERIC(10,2)')
        add_column_if_not_exists('ml_raw_player_data', 'jugador_fk', 'BIGINT')
        add_column_if_not_exists('ml_raw_player_data', 'equipo_fk', 'BIGINT')

    create_table_if_not_exists('ml_inference_ready_player_data', """
        CREATE TABLE IF NOT EXISTS ml_inference_ready_player_data (
            id SERIAL PRIMARY KEY,
            player_name VARCHAR(100) NOT NULL,
            team_name VARCHAR(100) NOT NULL,
            deporte VARCHAR(50) DEFAULT 'futbol',
            photo_url VARCHAR(500),
            logo_url VARCHAR(500),
            playing_time_min_scaled NUMERIC(10,5),
            total_shots_scaled NUMERIC(10,5),
            standard_sot_scaled NUMERIC(10,5),
            xg_scaled NUMERIC(10,5),
            pts_scaled NUMERIC(10,5),
            reb_scaled NUMERIC(10,5),
            ast_scaled NUMERIC(10,5),
            performance_gls NUMERIC(10,2),
            raw_data_id INTEGER,
            scaler_id INTEGER,
            jugador_fk BIGINT,
            equipo_fk BIGINT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    if table_exists('ml_inference_ready_player_data'):
        add_column_if_not_exists('ml_inference_ready_player_data', 'deporte', "VARCHAR(50) DEFAULT 'futbol'")
        add_column_if_not_exists('ml_inference_ready_player_data', 'xg_scaled', 'NUMERIC(10,5)')
        add_column_if_not_exists('ml_inference_ready_player_data', 'pts_scaled', 'NUMERIC(10,5)')
        add_column_if_not_exists('ml_inference_ready_player_data', 'reb_scaled', 'NUMERIC(10,5)')
        add_column_if_not_exists('ml_inference_ready_player_data', 'ast_scaled', 'NUMERIC(10,5)')
        add_column_if_not_exists('ml_inference_ready_player_data', 'scaler_id', 'INTEGER')
        add_column_if_not_exists('ml_inference_ready_player_data', 'jugador_fk', 'BIGINT')
        add_column_if_not_exists('ml_inference_ready_player_data', 'equipo_fk', 'BIGINT')

    print("  OK Tablas nuevas creadas.")

    # ── 6. Stats tables ──
    print("\n[6/7] Verificando tablas de stats...")

    rename_column_if_exists('stats_futbol', 'partido_id', 'id_partido')
    rename_column_if_exists('stats_nba', 'partido_id', 'id_partido')
    rename_column_if_exists('stats_mlb', 'partido_id', 'id_partido')

    rename_column_if_exists('stats_jugador_futbol', 'partido_id', 'id_partido')
    rename_column_if_exists('stats_jugador_futbol', 'jugador_id', 'id_jugador')
    rename_column_if_exists('stats_jugador_nba', 'partido_id', 'id_partido')
    rename_column_if_exists('stats_jugador_nba', 'jugador_id', 'id_jugador')
    rename_column_if_exists('stats_jugador_mlb', 'partido_id', 'id_partido')
    rename_column_if_exists('stats_jugador_mlb', 'jugador_id', 'id_jugador')

    print("  OK Tablas de stats verificadas.")

    # ── 7. Otros ajustes ──
    print("\n[7/7] Ajustes finales...")

    # Agregar columnas opcionales a tabla_general
    if table_exists('tabla_general'):
        add_column_if_not_exists('tabla_general', 'id_equipo', 'BIGINT')

    # Verificar tabla jugadores
    if table_exists('jugadores'):
        rename_column_if_exists('jugadores', 'equipo_id', 'id_equipo')

    print("  OK Ajustes finales completados.")

    print("\n" + "=" * 60)
    print(" MIGRACION DE SCHEMA COMPLETADA")
    print("=" * 60)
    print("\nAhora puedes ejecutar: python repoblar_bd.py --todo")


if __name__ == "__main__":
    migrate()
