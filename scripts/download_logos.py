"""
download_logos.py — Descarga de logos de equipos y ligas

Fuentes:
  - ESPN API: Logos de equipos (todas las ligas)
  - URLs publicas: Logos de ligas

Uso:
    python scripts/download_logos.py --todo
    python scripts/download_logos.py --solo-equipos
    python scripts/download_logos.py --solo-ligas
    python scripts/download_logos.py --local
"""

import os
import sys
import logging
import argparse
import json
import time
from pathlib import Path
from datetime import datetime

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.models import Team
from database import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("DownloadLogos")

LOGOS_DIR = PROJECT_ROOT / "media" / "logos" / "equipos"
LOGOS_DIR.mkdir(parents=True, exist_ok=True)

LEAGUE_LOGOS_DIR = PROJECT_ROOT / "media" / "logos" / "ligas"
LEAGUE_LOGOS_DIR.mkdir(parents=True, exist_ok=True)

ESPN_LEAGUES = [
    {"league_name": "Premier League", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams?limit=100"},
    {"league_name": "La Liga", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/teams?limit=100"},
    {"league_name": "Liga MX", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/teams?limit=100"},
    {"league_name": "NBA", "url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams?limit=100"},
    {"league_name": "MLB", "url": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams?limit=100"},
    {"league_name": "Bundesliga", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/teams?limit=100"},
    {"league_name": "Serie A", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/teams?limit=100"},
    {"league_name": "Ligue 1", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/teams?limit=100"},
]

LEAGUE_LOGOS = {
    "Premier League": "https://logos-world.net/wp-content/uploads/2020/06/Premier-League-Logo.png",
    "La Liga": "https://logos-world.net/wp-content/uploads/2020/06/La-Liga-Logo.png",
    "Bundesliga": "https://logos-world.net/wp-content/uploads/2020/06/Bundesliga-Logo.png",
    "Serie A": "https://logos-world.net/wp-content/uploads/2020/06/Serie-A-Logo.png",
    "Ligue 1": "https://logos-world.net/wp-content/uploads/2020/06/Ligue-1-Logo.png",
    "Liga MX": "https://img.azscore.com/soccer/league/229.png",
    "NBA": "https://logos-world.net/wp-content/uploads/2020/11/NBA-Logo.png",
    "MLB": "https://logos-world.net/wp-content/uploads/2020/11/MLB-Logo.png",
    "Champions League": "https://logos-world.net/wp-content/uploads/2020/06/Champions-League-Logo.png",
}


def sanitize_filename(name: str) -> str:
    """Convierte un nombre de equipo en un nombre de archivo seguro."""
    return (
        name.lower()
        .replace(' ', '_')
        .replace('.', '')
        .replace(',', '')
        .replace("'", '')
        .replace('/', '_')
        .replace('(', '')
        .replace(')', '')
        .replace('&', 'and')
        .strip('_')
    ) + ".png"


def download_image(url: str, save_path: Path) -> bool:
    """Descarga una imagen desde una URL y la guarda."""
    if not url:
        return False

    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.status_code == 200 and len(resp.content) > 500:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception as e:
        logger.debug(f"Error descargando {url}: {e}")

    return False


# ──────────────────────────────────────────────────────────────────────────────
# DESCARGAR LOGOS DE EQUIPOS DESDE ESPN
# ──────────────────────────────────────────────────────────────────────────────

def descargar_logos_equipos():
    """Descarga logos de todos los equipos desde ESPN y actualiza la BD."""
    logger.info("[LOGOS] Descargando logos de equipos desde ESPN...")

    total_descargados = 0
    total_actualizados = 0

    for config in ESPN_LEAGUES:
        logger.info(f"  Liga: {config['league_name']}...")

        try:
            resp = requests.get(config["url"], timeout=15)
            if resp.status_code != 200:
                continue

            data = resp.json()
            teams = data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])

            for item in teams:
                t = item.get('team', {})
                nombre = t.get('displayName', t.get('name', ''))
                logos = t.get('logos', [])
                logo_url = logos[0].get('href', '') if logos else ''

                if not logo_url or not nombre:
                    continue

                filename = sanitize_filename(nombre)
                local_path = LOGOS_DIR / filename

                if local_path.exists():
                    logger.debug(f"  Ya existe: {filename}")
                    continue

                if download_image(logo_url, local_path):
                    total_descargados += 1
                    logger.info(f"  Descargado: {filename}")

                    with Session(engine) as session:
                        result = session.execute(
                            text("UPDATE equipos SET logo_url = :url WHERE LOWER(nombre) = :nombre"),
                            {"url": f"/media/logos/equipos/{filename}", "nombre": nombre.lower()}
                        )
                        session.commit()
                        if result.rowcount > 0:
                            total_actualizados += 1

                time.sleep(0.3)

        except Exception as e:
            logger.error(f"  Error con {config['league_name']}: {e}")

    logger.info(f"[LOGOS] {total_descargados} logos descargados, {total_actualizados} equipos actualizados en BD.")


# ──────────────────────────────────────────────────────────────────────────────
# DESCARGAR LOGOS DE LIGAS
# ──────────────────────────────────────────────────────────────────────────────

def descargar_logos_ligas():
    """Descarga logos de ligas y genera un archivo JSON de referencia."""
    logger.info("[LOGOS] Descargando logos de ligas...")

    logos_guardados = {}

    for liga_name, url in LEAGUE_LOGOS.items():
        filename = sanitize_filename(liga_name)
        local_path = LEAGUE_LOGOS_DIR / filename

        if local_path.exists():
            logger.debug(f"  Ya existe: {filename}")
            logos_guardados[liga_name] = f"/media/logos/ligas/{filename}"
            continue

        if download_image(url, local_path):
            logos_guardados[liga_name] = f"/media/logos/ligas/{filename}"
            logger.info(f"  Descargado: {filename}")
        else:
            logger.warning(f"  No se pudo descargar: {liga_name}")

        time.sleep(0.5)

    config_path = LEAGUE_LOGOS_DIR / "league_logos.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(logos_guardados, f, indent=2, ensure_ascii=False)

    logger.info(f"[LOGOS] {len(logos_guardados)} logos de ligas guardados.")


# ──────────────────────────────────────────────────────────────────────────────
# DESCARGAR LOGOS PARA EQUIPOS EXISTENTES EN BD
# ──────────────────────────────────────────────────────────────────────────────

def descargar_logos_equipos_bd():
    """Descarga logos para equipos que ya estan en la BD pero sin logo_url."""
    logger.info("[LOGOS] Descargando logos para equipos existentes en BD...")

    # Mapeo de nombres abreviados a nombres ESPN
    NAME_MAP = {
        # La Liga
        'alaves': 'Alavés',
        'ath bilbao': 'Athletic Club',
        'ath madrid': 'Atlético Madrid',
        'betis': 'Real Betis',
        'celta': 'Celta Vigo',
        'espanol': 'Espanyol',
        'oviedo': 'Real Oviedo',
        'sociedad': 'Real Sociedad',
        'vallecano': 'Rayo Vallecano',
        # Premier League
        'bournemouth': 'AFC Bournemouth',
        'brighton': 'Brighton & Hove Albion',
        'leeds': 'Leeds United',
        'man city': 'Manchester City',
        'man united': 'Manchester United',
        'newcastle': 'Newcastle United',
        "nott'm forest": 'Nottingham Forest',
        'tottenham': 'Tottenham Hotspur',
        'west ham': 'West Ham United',
        'wolves': 'Wolverhampton Wanderers',
        # Bundesliga
        'augsburg': 'FC Augsburg',
        'dortmund': 'Borussia Dortmund',
        'ein frankfurt': 'Eintracht Frankfurt',
        'fc koln': 'FC Cologne',
        'freiburg': 'SC Freiburg',
        'hamburg': 'Hamburg SV',
        'heidenheim': '1. FC Heidenheim 1846',
        'hoffenheim': 'TSG Hoffenheim',
        'leverkusen': 'Bayer Leverkusen',
        "m'gladbach": 'Borussia Mönchengladbach',
        'st pauli': 'St. Pauli',
        'stuttgart': 'VfB Stuttgart',
        'union berlin': '1. FC Union Berlin',
        'wolfsburg': 'VfL Wolfsburg',
        # Serie A
        'inter': 'Internazionale',
        'milan': 'AC Milan',
        'roma': 'AS Roma',
        'verona': 'Hellas Verona',
        # Ligue 1
        'auxerre': 'AJ Auxerre',
        'le havre': 'Le Havre AC',
        'monaco': 'AS Monaco',
        'paris sg': 'Paris Saint-Germain',
        'rennes': 'Stade Rennais',
    }

    with Session(engine) as session:
        equipos_sin_logo = session.execute(
            text("SELECT id_equipo, nombre, liga FROM equipos WHERE logo_url IS NULL OR logo_url = ''")
        ).fetchall()

        if not equipos_sin_logo:
            logger.info("[LOGOS] Todos los equipos tienen logo.")
            return

        logger.info(f"[LOGOS] {len(equipos_sin_logo)} equipos sin logo. Buscando en ESPN...")

        # Precargar todos los equipos de ESPN por liga
        espn_teams_by_league = {}
        for config in ESPN_LEAGUES:
            try:
                resp = requests.get(config["url"], timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    teams = data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])
                    espn_teams_by_league[config['league_name']] = {
                        t.get('team', {}).get('displayName', '').lower(): {
                            'logo': t.get('team', {}).get('logos', [{}])[0].get('href', ''),
                            'name': t.get('team', {}).get('displayName', ''),
                        }
                        for t in teams if t.get('team', {}).get('displayName')
                    }
            except Exception as e:
                logger.debug(f"  Error cargando {config['league_name']}: {e}")

        downloaded = 0
        for equipo in equipos_sin_logo:
            id_equipo, nombre, liga = equipo

            # Intentar con el mapeo directo primero
            espn_name = NAME_MAP.get(nombre.lower())

            if espn_name:
                # Buscar en todas las ligas de ESPN
                for league_name, teams in espn_teams_by_league.items():
                    if espn_name.lower() in teams:
                        logo_url = teams[espn_name.lower()]['logo']
                        if logo_url:
                            filename = sanitize_filename(nombre)
                            local_path = LOGOS_DIR / filename

                            if not local_path.exists():
                                if download_image(logo_url, local_path):
                                    downloaded += 1

                            session.execute(
                                text("UPDATE equipos SET logo_url = :url WHERE id_equipo = :id"),
                                {"url": f"/media/logos/equipos/{filename}", "id": id_equipo}
                            )
                            session.commit()
                            logger.info(f"  Logo asignado: {nombre} -> {espn_name}")
                            break
                continue

            # Fallback: busqueda por substring
            for league_name, teams in espn_teams_by_league.items():
                if liga and league_name.lower() not in liga.lower():
                    continue

                for espn_lower, info in teams.items():
                    if nombre.lower() in espn_lower or espn_lower in nombre.lower():
                        logo_url = info['logo']
                        if logo_url:
                            filename = sanitize_filename(nombre)
                            local_path = LOGOS_DIR / filename

                            if not local_path.exists():
                                if download_image(logo_url, local_path):
                                    downloaded += 1

                            session.execute(
                                text("UPDATE equipos SET logo_url = :url WHERE id_equipo = :id"),
                                {"url": f"/media/logos/equipos/{filename}", "id": id_equipo}
                            )
                            session.commit()
                            logger.info(f"  Logo asignado (substring): {nombre} -> {info['name']}")
                            break

                time.sleep(0.3)

        logger.info(f"[LOGOS] {downloaded} logos descargados para equipos existentes.")


# ──────────────────────────────────────────────────────────────────────────────
# ORQUESTADOR
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Download Logos — It's Coming")
    parser.add_argument('--todo', action='store_true')
    parser.add_argument('--solo-equipos', action='store_true')
    parser.add_argument('--solo-ligas', action='store_true')
    parser.add_argument('--solo-bd', action='store_true', help="Solo equipos existentes en BD sin logo")

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info(" DOWNLOAD LOGOS")
    logger.info("=" * 50)

    if args.todo or args.solo_equipos:
        descargar_logos_equipos()

    if args.todo or args.solo_ligas:
        descargar_logos_ligas()

    if args.todo or args.solo_bd:
        descargar_logos_equipos_bd()

    logger.info("=" * 50)
    logger.info(" DOWNLOAD LOGOS COMPLETADO")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
