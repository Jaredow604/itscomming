import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from database import DB_URL

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_constraints():
    engine = create_engine(DB_URL)
    
    constraints_to_add = [
        # fbref_team_stats
        ("fbref_team_stats", "equipo_fk", "equipos", "id_equipo"),
        
        # fbref_player_stats
        ("fbref_player_stats", "equipo_fk", "equipos", "id_equipo"),
        ("fbref_player_stats", "jugador_fk", "jugadores", "id_jugador"),
        
        # nba_player_history
        ("nba_player_history", "equipo_fk", "equipos", "id_equipo"),
        ("nba_player_history", "jugador_fk", "jugadores", "id_jugador"),
        ("nba_player_history", "partido_fk", "partidos", "id_partido"),
        
        # nba_player_stats_clean
        ("nba_player_stats_clean", "equipo_fk", "equipos", "id_equipo"),
        ("nba_player_stats_clean", "jugador_fk", "jugadores", "id_jugador"),
        
        # ml_match_features
        ("ml_match_features", "equipo_fk", "equipos", "id_equipo"),
        ("ml_match_features", "partido_fk", "partidos", "id_partido"),
        
        # match_history_stats
        ("match_history_stats", "local_fk", "equipos", "id_equipo"),
        ("match_history_stats", "visitante_fk", "equipos", "id_equipo"),
        ("match_history_stats", "partido_fk", "partidos", "id_partido"),
    ]

    with engine.connect() as conn:
        logger.info("Iniciando creación de constraints de Foreign Key...")
        
        for table, column, ref_table, ref_column in constraints_to_add:
            constraint_name = f"fk_{table}_{column}"
            
            # Verificar si el constraint ya existe
            check_sql = text(f"""
                SELECT conname
                FROM pg_constraint
                WHERE conname = '{constraint_name}'
            """)
            result = conn.execute(check_sql).fetchone()
            
            if result:
                logger.info(f"OK: Constraint {constraint_name} ya existe en {table}.")
                continue
                
            alter_sql = text(f"""
                ALTER TABLE {table} 
                ADD CONSTRAINT {constraint_name} 
                FOREIGN KEY ({column}) REFERENCES {ref_table}({ref_column})
            """)
            
            try:
                conn.execute(alter_sql)
                conn.commit()
                logger.info(f"ÉXITO: Constraint {constraint_name} ({column} -> {ref_table}.{ref_column}) creado en {table}.")
            except IntegrityError as e:
                logger.error(f"ERROR DE INTEGRIDAD en {table}.{column}: Hay datos que violan la restricción y no existen en {ref_table}. Detalle: {e.orig}")
                conn.rollback() # Hacer rollback para poder seguir con los demás
            except Exception as e:
                logger.error(f"ERROR INESPERADO al crear constraint en {table}: {e}")
                conn.rollback()

if __name__ == '__main__':
    add_constraints()
