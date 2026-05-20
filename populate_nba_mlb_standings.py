"""
populate_nba_mlb_standings.py — Genera datos históricos de NBA y MLB para match_history_stats.

Crea partidos ficticios pero realistas basados en equipos existentes para que las tablas
de clasificación de NBA y MLB tengan datos.

Uso:
    python populate_nba_mlb_standings.py
"""

import sys
import os
import logging
import random
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Equipos NBA con sus IDs
NBA_TEAMS = [
    (200001, "Atlanta Hawks"),
    (200002, "Boston Celtics"),
    (200003, "New Orleans Pelicans"),
    (200004, "Chicago Bulls"),
    (200005, "Cleveland Cavaliers"),
    (200006, "Dallas Mavericks"),
    (200007, "Denver Nuggets"),
    (200008, "Detroit Pistons"),
    (200009, "Golden State Warriors"),
    (200010, "Houston Rockets"),
    (200011, "Indiana Pacers"),
    (200012, "LA Clippers"),
    (200013, "Los Angeles Lakers"),
    (200014, "Miami Heat"),
    (200015, "Milwaukee Bucks"),
    (200016, "Minnesota Timberwolves"),
    (200017, "Brooklyn Nets"),
    (200018, "New York Knicks"),
    (200019, "Orlando Magic"),
    (200020, "Philadelphia 76ers"),
    (200021, "Phoenix Suns"),
    (200022, "Portland Trail Blazers"),
    (200023, "Sacramento Kings"),
    (200024, "San Antonio Spurs"),
    (200025, "Oklahoma City Thunder"),
    (200026, "Utah Jazz"),
    (200027, "Washington Wizards"),
    (200028, "Toronto Raptors"),
    (200029, "Memphis Grizzlies"),
    (200030, "Charlotte Hornets"),
]

# Equipos MLB con sus IDs
MLB_TEAMS = [
    (300001, "Baltimore Orioles"),
    (300002, "Boston Red Sox"),
    (300003, "Los Angeles Angels"),
    (300004, "Chicago White Sox"),
    (300005, "Cleveland Guardians"),
    (300006, "Detroit Tigers"),
    (300007, "Kansas City Royals"),
    (300008, "Milwaukee Brewers"),
    (300009, "Minnesota Twins"),
    (300010, "New York Yankees"),
    (300011, "Athletics"),
    (300012, "Seattle Mariners"),
    (300013, "Texas Rangers"),
    (300014, "Toronto Blue Jays"),
    (300015, "Atlanta Braves"),
    (300016, "Chicago Cubs"),
    (300017, "Cincinnati Reds"),
    (300018, "Houston Astros"),
    (300019, "Los Angeles Dodgers"),
    (300020, "Washington Nationals"),
    (300021, "New York Mets"),
    (300022, "Philadelphia Phillies"),
    (300023, "Pittsburgh Pirates"),
    (300024, "St. Louis Cardinals"),
    (300025, "San Diego Padres"),
    (300026, "San Francisco Giants"),
    (300027, "Colorado Rockies"),
    (300028, "Miami Marlins"),
    (300029, "Arizona Diamondbacks"),
    (300030, "Tampa Bay Rays"),
]

def generate_nba_matches(session, num_matches=500):
    """Genera partidos de NBA ficticios."""
    logger.info(f"Generando {num_matches} partidos de NBA...")
    
    # Obtener el max ID actual
    max_id_result = session.execute(text("SELECT MAX(id) FROM match_history_stats")).fetchone()
    next_id = (max_id_result[0] or 0) + 1
    
    inserted = 0
    start_date = datetime(2025, 10, 1)
    
    for i in range(num_matches):
        # Seleccionar dos equipos aleatorios diferentes
        home_team = random.choice(NBA_TEAMS)
        away_team = random.choice([t for t in NBA_TEAMS if t[0] != home_team[0]])
        
        # Generar scores realistas de NBA (80-130 puntos)
        home_score = random.randint(95, 125)
        away_score = random.randint(90, 120)
        
        # Fecha aleatoria en la temporada 2025-26
        game_date = start_date + timedelta(days=random.randint(0, 180))
        
        # Determinar resultado (1=home win, 2=away win, 3=draw - pero NBA no tiene empates)
        result = 1 if home_score > away_score else 2
        
        session.execute(text("""
            INSERT INTO match_history_stats (
                id, league, season, date, home_team, away_team,
                home_score, away_score, home_xg, away_xg,
                home_form_gf, home_form_ga, away_form_gf, away_form_ga,
                total_goals, result, local_fk, visitante_fk, partido_fk,
                home_form_xgf, home_form_xga, away_form_xgf, away_form_xga
            ) VALUES (
                :id, 'NBA', '25-26', :date, :home_team, :away_team,
                :home_score, :away_score, :home_xg, :away_xg,
                :home_form_gf, :home_form_ga, :away_form_gf, :away_form_ga,
                :total_goals, :result, :local_fk, :visitante_fk, NULL,
                :home_form_xgf, :home_form_xga, :away_form_xgf, :away_form_xga
            )
            ON CONFLICT (home_team, away_team, date) DO NOTHING
        """), {
            "id": next_id,
            "date": game_date,
            "home_team": home_team[1],
            "away_team": away_team[1],
            "home_score": home_score,
            "away_score": away_score,
            "home_xg": home_score * 0.1,
            "away_xg": away_score * 0.1,
            "home_form_gf": home_score * 0.8,
            "home_form_ga": away_score * 0.8,
            "away_form_gf": away_score * 0.8,
            "away_form_ga": home_score * 0.8,
            "total_goals": home_score + away_score,
            "result": result,
            "local_fk": home_team[0],
            "visitante_fk": away_team[0],
            "home_form_xgf": home_score * 0.1,
            "home_form_xga": away_score * 0.1,
            "away_form_xgf": away_score * 0.1,
            "away_form_xga": home_score * 0.1,
        })
        
        next_id += 1
        inserted += 1
        
        if inserted % 100 == 0:
            session.commit()
            logger.info(f"  Insertados: {inserted}/{num_matches}")
    
    session.commit()
    logger.info(f"  Total insertados: {inserted}")
    return inserted

def generate_mlb_matches(session, num_matches=500):
    """Genera partidos de MLB ficticios."""
    logger.info(f"Generando {num_matches} partidos de MLB...")
    
    # Obtener el max ID actual
    max_id_result = session.execute(text("SELECT MAX(id) FROM match_history_stats")).fetchone()
    next_id = (max_id_result[0] or 0) + 1
    
    inserted = 0
    start_date = datetime(2025, 4, 1)
    
    for i in range(num_matches):
        # Seleccionar dos equipos aleatorios diferentes
        home_team = random.choice(MLB_TEAMS)
        away_team = random.choice([t for t in MLB_TEAMS if t[0] != home_team[0]])
        
        # Generar scores realistas de MLB (0-15 carreras)
        home_score = random.randint(0, 12)
        away_score = random.randint(0, 10)
        
        # Fecha aleatoria en la temporada 2025
        game_date = start_date + timedelta(days=random.randint(0, 180))
        
        # Determinar resultado
        result = 1 if home_score > away_score else 2
        
        session.execute(text("""
            INSERT INTO match_history_stats (
                id, league, season, date, home_team, away_team,
                home_score, away_score, home_xg, away_xg,
                home_form_gf, home_form_ga, away_form_gf, away_form_ga,
                total_goals, result, local_fk, visitante_fk, partido_fk,
                home_form_xgf, home_form_xga, away_form_xgf, away_form_xga
            ) VALUES (
                :id, 'MLB', '25-26', :date, :home_team, :away_team,
                :home_score, :away_score, :home_xg, :away_xg,
                :home_form_gf, :home_form_ga, :away_form_gf, :away_form_ga,
                :total_goals, :result, :local_fk, :visitante_fk, NULL,
                :home_form_xgf, :home_form_xga, :away_form_xgf, :away_form_xga
            )
            ON CONFLICT (home_team, away_team, date) DO NOTHING
        """), {
            "id": next_id,
            "date": game_date,
            "home_team": home_team[1],
            "away_team": away_team[1],
            "home_score": home_score,
            "away_score": away_score,
            "home_xg": home_score * 0.1,
            "away_xg": away_score * 0.1,
            "home_form_gf": home_score * 0.8,
            "home_form_ga": away_score * 0.8,
            "away_form_gf": away_score * 0.8,
            "away_form_ga": home_score * 0.8,
            "total_goals": home_score + away_score,
            "result": result,
            "local_fk": home_team[0],
            "visitante_fk": away_team[0],
            "home_form_xgf": home_score * 0.1,
            "home_form_xga": away_score * 0.1,
            "away_form_xgf": away_score * 0.1,
            "away_form_xga": home_score * 0.1,
        })
        
        next_id += 1
        inserted += 1
        
        if inserted % 100 == 0:
            session.commit()
            logger.info(f"  Insertados: {inserted}/{num_matches}")
    
    session.commit()
    logger.info(f"  Total insertados: {inserted}")
    return inserted

def main():
    logger.info("=" * 60)
    logger.info("Generando datos de NBA y MLB para standings")
    logger.info("=" * 60)
    
    session = SessionLocal()
    try:
        # Generar partidos de NBA
        nba_inserted = generate_nba_matches(session, num_matches=500)
        
        # Generar partidos de MLB
        mlb_inserted = generate_mlb_matches(session, num_matches=500)
        
        # Resumen
        logger.info("=" * 60)
        logger.info("RESUMEN")
        logger.info("=" * 60)
        logger.info(f"NBA partidos generados: {nba_inserted}")
        logger.info(f"MLB partidos generados: {mlb_inserted}")
        
    finally:
        session.close()

if __name__ == "__main__":
    main()
