"""
populate_daily_schedule.py -- Pobla dailyschedule con partidos de hoy desde APIs externas.

Pipeline:
1. Consulta ESPN API para partidos de hoy (NBA, MLB, Soccer)
2. Inserta en dailyschedule via SQLAlchemy
3. Actualiza FKs a equipos si existen
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime, date

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database import SessionLocal
from src.data.models import DailySchedule, Team

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_team_fk(session, team_name: str) -> int | None:
    """Busca el id_equipo por nombre (con fallback fuzzy)."""
    team = session.query(Team).filter(Team.nombre == team_name).first()
    if team:
        return team.id_equipo
    # Fallback: búsqueda parcial
    team = session.query(Team).filter(Team.nombre.ilike(f"%{team_name}%")).first()
    return team.id_equipo if team else None


def populate_from_espn():
    """Consulta ESPN API para partidos de hoy."""
    session = SessionLocal()
    try:
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')

        # ESPN endpoints para hoy (formato YYYYMMDD)
        today_espn = today.strftime('%Y%m%d')
        endpoints = [
            ('nba', 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={}'.format(today_espn)),
            ('mlb', 'https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={}'.format(today_espn)),
            ('soccer', 'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates={}'.format(today_espn)),
        ]

        import httpx

        total_inserted = 0
        for sport, url in endpoints:
            try:
                response = httpx.get(url, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                events = data.get('events', [])
                for event in events:
                    home_team = event.get('competitions', [{}])[0].get('competitors', [{}])[0].get('team', {}).get('displayName', '')
                    away_team = event.get('competitions', [{}])[0].get('competitors', [{}])[1].get('team', {}).get('displayName', '')

                    if not home_team or not away_team:
                        continue

                    # Verificar si ya existe
                    existing = session.query(DailySchedule).filter(
                        DailySchedule.sport == sport,
                        DailySchedule.home_team == home_team,
                        DailySchedule.away_team == away_team,
                        DailySchedule.match_date == today,
                    ).first()

                    if existing:
                        continue

                    # Obtener hora del partido
                    start_time = None
                    date_str = event.get('date', '')
                    if date_str:
                        try:
                            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            start_time = dt
                        except Exception:
                            pass

                    # Crear registro
                    schedule = DailySchedule(
                        sport=sport,
                        home_team=home_team,
                        away_team=away_team,
                        match_date=today,
                        start_time=start_time,
                        equipo_local_fk=get_team_fk(session, home_team),
                        equipo_visitante_fk=get_team_fk(session, away_team),
                    )
                    session.add(schedule)
                    total_inserted += 1
                    logger.info(f"[{sport}] {home_team} vs {away_team}")

            except Exception as e:
                logger.warning(f"Error consultando {sport}: {e}")

        session.commit()
        logger.info(f"Total partidos insertados: {total_inserted}")
        return total_inserted

    except Exception as e:
        session.rollback()
        logger.error(f"Error en populate_daily_schedule: {e}")
        return 0
    finally:
        session.close()


def main():
    logger.info("=" * 60)
    logger.info("Poblando DailySchedule con partidos de hoy")
    logger.info("=" * 60)

    count = populate_from_espn()
    logger.info(f"Proceso completado. {count} partidos insertados.")


if __name__ == '__main__':
    main()
