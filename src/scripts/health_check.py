import os
import sys
import logging

# Configurar path para imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database import SessionLocal
from src.data.models import (
    Team, Player, Match, MatchStatsNBA, MatchStatsMLB, MatchStatsFutbol,
    PlayerStatsNBA, PlayerStatsMLB, PlayerStatsFutbol, LeagueTable,
    FBrefTeamStats, FBrefPlayerStats, NBAPlayerHistory, NBAPlayerStatsClean,
    MLMatchFeatures, MatchHistoryStats
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_health_check():
    session = SessionLocal()
    
    modelos = [
        Team, Player, Match, MatchStatsNBA, MatchStatsMLB, MatchStatsFutbol,
        PlayerStatsNBA, PlayerStatsMLB, PlayerStatsFutbol, LeagueTable,
        FBrefTeamStats, FBrefPlayerStats, NBAPlayerHistory, NBAPlayerStatsClean,
        MLMatchFeatures, MatchHistoryStats
    ]
    
    logger.info("=== Iniciando ORM Health-Check en PostgreSQL ===")
    
    errores = 0
    for modelo in modelos:
        try:
            registro = session.query(modelo).first()
            if registro:
                logger.info(f"OK: Éxito al leer {modelo.__name__} ({modelo.__tablename__})")
            else:
                logger.info(f"WARNING: {modelo.__name__} ({modelo.__tablename__}) está VACÍA, pero el mapping ORM es válido.")
        except Exception as e:
            logger.error(f"ERROR: Fallo en el modelo {modelo.__name__} ({modelo.__tablename__}): {e}")
            errores += 1
            session.rollback()
            
    session.close()
    
    if errores == 0:
        logger.info("\n🏆 Health-Check Completado: 0 errores detectados. El mapeo ORM es perfecto.")
    else:
        logger.warning(f"\n💥 Health-Check Finalizado con {errores} errores. Revisa los logs.")

if __name__ == '__main__':
    run_health_check()
