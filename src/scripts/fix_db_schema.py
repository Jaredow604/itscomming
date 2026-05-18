import os
import sys
import logging
from sqlalchemy import create_engine, text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from database import DB_URL

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_schema():
    engine = create_engine(DB_URL)
    
    with engine.connect() as conn:
        logger.info("Añadiendo llaves foráneas y primary keys faltantes a Postgres...")
        
        # fbref_team_stats
        try:
            conn.execute(text("ALTER TABLE fbref_team_stats ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;"))
            conn.execute(text("ALTER TABLE fbref_team_stats ADD COLUMN IF NOT EXISTS equipo_fk INTEGER;"))
            logger.info("fbref_team_stats fixed")
        except Exception as e: logger.error(f"fbref_team_stats: {e}")

        # fbref_player_stats
        try:
            conn.execute(text("ALTER TABLE fbref_player_stats ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;"))
            conn.execute(text("ALTER TABLE fbref_player_stats ADD COLUMN IF NOT EXISTS equipo_fk INTEGER;"))
            conn.execute(text("ALTER TABLE fbref_player_stats ADD COLUMN IF NOT EXISTS jugador_fk INTEGER;"))
            logger.info("fbref_player_stats fixed")
        except Exception as e: logger.error(f"fbref_player_stats: {e}")

        # nba_player_history
        try:
            conn.execute(text("ALTER TABLE nba_player_history ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;"))
            conn.execute(text("ALTER TABLE nba_player_history ADD COLUMN IF NOT EXISTS equipo_fk INTEGER;"))
            conn.execute(text("ALTER TABLE nba_player_history ADD COLUMN IF NOT EXISTS jugador_fk INTEGER;"))
            conn.execute(text("ALTER TABLE nba_player_history ADD COLUMN IF NOT EXISTS partido_fk INTEGER;"))
            logger.info("nba_player_history fixed")
        except Exception as e: logger.error(f"nba_player_history: {e}")

        # nba_player_stats_clean (has 'id' already, maybe missing fks and 'team_name' and 'player_name')
        # Wait, the inspect showed it has `nombre_jugador`, not `player_name`. 
        try:
            conn.execute(text("ALTER TABLE nba_player_stats_clean ADD COLUMN IF NOT EXISTS equipo_fk INTEGER;"))
            conn.execute(text("ALTER TABLE nba_player_stats_clean ADD COLUMN IF NOT EXISTS jugador_fk INTEGER;"))
            conn.execute(text("ALTER TABLE nba_player_stats_clean ADD COLUMN IF NOT EXISTS team_name TEXT;"))
            conn.execute(text("ALTER TABLE nba_player_stats_clean RENAME COLUMN nombre_jugador TO player_name;"))
            logger.info("nba_player_stats_clean fixed")
        except Exception as e: logger.error(f"nba_player_stats_clean: {e}")

        # ml_match_features
        try:
            conn.execute(text("ALTER TABLE ml_match_features ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;"))
            conn.execute(text("ALTER TABLE ml_match_features ADD COLUMN IF NOT EXISTS equipo_fk INTEGER;"))
            conn.execute(text("ALTER TABLE ml_match_features ADD COLUMN IF NOT EXISTS partido_fk INTEGER;"))
            logger.info("ml_match_features fixed")
        except Exception as e: logger.error(f"ml_match_features: {e}")

        # match_history_stats
        try:
            conn.execute(text("ALTER TABLE match_history_stats ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;"))
            conn.execute(text("ALTER TABLE match_history_stats ADD COLUMN IF NOT EXISTS local_fk INTEGER;"))
            conn.execute(text("ALTER TABLE match_history_stats ADD COLUMN IF NOT EXISTS visitante_fk INTEGER;"))
            conn.execute(text("ALTER TABLE match_history_stats ADD COLUMN IF NOT EXISTS partido_fk INTEGER;"))
            logger.info("match_history_stats fixed")
        except Exception as e: logger.error(f"match_history_stats: {e}")

        conn.commit()
        logger.info("DB Schema Fix Completed.")

if __name__ == '__main__':
    fix_schema()
