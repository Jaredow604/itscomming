"""
arrancar.py — Bootstrap inicial de equipos y logos desde ESPN API

Uso:
    python arrancar.py
"""

import sys
import os
import requests
from sqlalchemy.orm import Session

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from database import SessionLocal
from src.data.models import Team, AliasEquipo

ESPN_CONFIG = [
    {"league_name": "Premier League", "sport": "soccer", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams?limit=100"},
    {"league_name": "La Liga", "sport": "soccer", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/teams?limit=100"},
    {"league_name": "Liga MX", "sport": "soccer", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/teams?limit=100"},
    {"league_name": "NBA", "sport": "basketball", "prefix": 200000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams?limit=100"},
    {"league_name": "MLB", "sport": "baseball", "prefix": 300000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams?limit=100"},
    {"league_name": "Bundesliga", "sport": "soccer", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/teams?limit=100"},
    {"league_name": "Serie A", "sport": "soccer", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/teams?limit=100"},
    {"league_name": "Ligue 1", "sport": "soccer", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/teams?limit=100"},
]


def crear_alias(session, nombre_fuente: str, id_equipo: int):
    """Crea un alias si no existe."""
    from sqlalchemy import text
    existing = session.execute(
        text("SELECT id FROM alias_equipos WHERE nombre_fuente = :n"),
        {"n": nombre_fuente.lower().strip()}
    ).fetchone()
    if not existing:
        session.execute(
            text("INSERT INTO alias_equipos (nombre_fuente, id_equipo) VALUES (:n, :id)"),
            {"n": nombre_fuente.lower().strip(), "id": id_equipo}
        )


def bootstrap_leagues_and_teams():
    print("🚀 Iniciando inyección de entidades base y logos (ESPN)...")
    db = SessionLocal()
    total_teams_added = 0

    try:
        for config in ESPN_CONFIG:
            print(f"📦 Extrayendo: {config['league_name']}...")
            response = requests.get(config["url"], timeout=15)
            if response.status_code != 200:
                print(f"⚠️ Error HTTP con {config['league_name']}")
                continue

            data = response.json()
            teams_array = data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])

            teams_in_league = 0
            for item in teams_array:
                t_data = item.get('team', {})
                espn_id = int(t_data.get('id', 0))
                id_canonical = config["prefix"] + espn_id

                nombre_completo = t_data.get('displayName', t_data.get('name', ''))
                logos = t_data.get('logos', [])
                logo = logos[0].get('href', '') if logos else None

                existing_team = db.query(Team).filter(Team.id_equipo == id_canonical).first()

                if not existing_team:
                    new_team = Team(
                        id_equipo=id_canonical,
                        nombre=nombre_completo,
                        liga=config["league_name"],
                        logo_url=logo,
                    )
                    db.add(new_team)
                    db.flush()

                    crear_alias(db, nombre_completo, id_canonical)

                    nombre_corto = t_data.get('shortDisplayName', '')
                    if nombre_corto and nombre_corto != nombre_completo:
                        crear_alias(db, nombre_corto, id_canonical)

                    teams_in_league += 1
                    total_teams_added += 1

            db.commit()
            print(f"   ✅ {teams_in_league} equipos guardados.")

        print(f"\n🎉 EXTRACCIÓN EXITOSA: {total_teams_added} registros insertados.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error al guardar en base de datos: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    bootstrap_leagues_and_teams()
