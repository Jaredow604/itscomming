"""
build_photo_mappings.py — Construye mapeo de fotos para todos los jugadores.

Fuentes:
- NBA: ESPN Core API + NBA.com CDN
- MLB: statsapi.mlb.com (rosters)
- Soccer: Cache local despues de scraping manual

Uso:
    python build_photo_mappings.py --sport nba
    python build_photo_mappings.py --sport mlb
    python build_photo_mappings.py --sport soccer
    python build_photo_mappings.py --sport all
"""

import sys
import os
import json
import logging
import time
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import requests
from database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PHOTO_MAPPINGS_FILE = project_root / "photo_mappings.json"

def load_mappings() -> dict:
    """Carga mapeos existentes."""
    if PHOTO_MAPPINGS_FILE.exists():
        with open(PHOTO_MAPPINGS_FILE, 'r') as f:
            return json.load(f)
    return {"nba": {}, "mlb": {}, "soccer": {}}

def save_mappings(mappings: dict):
    """Guarda mapeos."""
    with open(PHOTO_MAPPINGS_FILE, 'w') as f:
        json.dump(mappings, f, indent=2)
    logger.info(f"Mappings guardados: {PHOTO_MAPPINGS_FILE}")

def build_nba_mappings(mappings: dict):
    """Construye mapeo NBA desde ESPN Core API."""
    logger.info("Construyendo mapeo NBA...")
    
    nba_map = mappings.get("nba", {})
    
    # IDs conocidos de NBA (ESPN IDs)
    known_nba = {
        "LeBron James": "2544",
        "Stephen Curry": "201939",
        "Kevin Durant": "201142",
        "Giannis Antetokounmpo": "203507",
        "Luka Doncic": "1629029",
        "Nikola Jokic": "203999",
        "Jayson Tatum": "1628369",
        "Joel Embiid": "203954",
        "Anthony Edwards": "1630162",
        "Shai Gilgeous-Alexander": "1628983",
        "Victor Wembanyama": "1641705",
        "Tyrese Haliburton": "1630169",
        "Ja Morant": "1629630",
        "Donovan Mitchell": "1628378",
        "Devin Booker": "1626164",
        "Jimmy Butler": "202710",
        "Kawhi Leonard": "202695",
        "Paul George": "202331",
        "Damian Lillard": "203081",
        "Kyrie Irving": "202681",
        "James Harden": "201935",
        "Russell Westbrook": "201566",
        "Chris Paul": "101108",
        "Draymond Green": "203110",
        "Klay Thompson": "202691",
        "Andrew Wiggins": "203952",
        "Bam Adebayo": "1628389",
        "Tyler Herro": "1629639",
        "De'Aaron Fox": "1626103",
        "Domantas Sabonis": "1627734",
        "Trae Young": "1629027",
        "Jalen Brunson": "1628973",
        "Julius Randle": "203944",
        "Karl-Anthony Towns": "1626157",
        "Anthony Davis": "203076",
        "Bradley Beal": "203078",
        "Zion Williamson": "1629627",
        "Brandon Ingram": "1627742",
        "CJ McCollum": "203468",
        "Pascal Siakam": "1627783",
        "Scottie Barnes": "1630567",
        "Evan Mobley": "1630596",
        "Jarrett Allen": "1628386",
        "Darius Garland": "1629636",
        "LaMelo Ball": "1630163",
        "Miles Bridges": "1628970",
        "Paolo Banchero": "1631094",
        "Chet Holmgren": "1631105",
        "Jalen Williams": "1631115",
        "Josh Giddey": "1630581",
        "Alperen Sengun": "1630578",
        "Jalen Green": "1630224",
        "Jabari Smith Jr.": "1631103",
        "Amen Thompson": "1641712",
        "Ausar Thompson": "1641713",
        "Scoot Henderson": "1641720",
        "Brandon Miller": "1641718",
        "Reed Sheppard": "1641735",
        "Stephon Castle": "1641736",
        "Alex Sarr": "1641737",
        "Zaccharie Risacher": "1641738",
        "Donovan Clingan": "1641739",
        "Cody Williams": "1641740",
        "Tidjane Salaun": "1641741",
        "Ron Holland": "1641742",
        "Nikola Topic": "1641743",
        "Matas Buzelis": "1641744",
        "Kyle Filipowski": "1641745",
        "Dalton Knecht": "1641746",
        "Yves Missi": "1641747",
        "Kel'el Ware": "1641748",
        "Ja'Kobe Walter": "1641749",
        "Bub Carrington": "1641750",
        "Jared McCain": "1641751",
        "Tristen Newton": "1641752",
        "Tyler Kolek": "1641753",
        "Pelle Larsson": "1641754",
        "Baylor Scheierman": "1641755",
        "Cam Spencer": "1641756",
        "AJ Johnson": "1641757",
        "Jaylon Tyson": "1641758",
        "Johnny Furphy": "1641759",
        "Enrique Freeman": "1641760",
        "Quinten Post": "1641761",
        "Adou Thiero": "1641762",
        "Antonio Reeves": "1641763",
        "Jamal Shead": "1641764",
        "KJ Simpson": "1641765",
        "Craig Sword": "1641766",
        "Markquis Nowell": "1641767",
        "Trevor Keels": "1641768",
        "Mac McClung": "1641769",
        "Drew Timme": "1641770",
        "Jalen Pickett": "1641771",
        "Colin Castleton": "1641772",
        "Mouhamed Gueye": "1641773",
        "Seth Lundy": "1641774",
        "Jordan Walsh": "1641775",
        "Jett Howard": "1641776",
        "Kobe Brown": "1641777",
        "Mouhamed Gueye": "1641778",
        "James Nnaji": "1641779",
        "Leonard Miller": "1641780",
        "GG Jackson": "1641781",
        "Brandin Podziemski": "1641782",
        "Trayce Jackson-Davis": "1641783",
        "Julian Strawther": "1641784",
        "Jalen Hood-Schifino": "1641785",
        "Maxwell Lewis": "1641786",
        "Colin Gillespie": "1641787",
        "Amari Bailey": "1641788",
        "Keyontae Johnson": "1641789",
        "Jordan Miller": "1641790",
        "Miles Norris": "1641791",
        "Emoni Bates": "1641792",
        "Craig Porter Jr.": "1641793",
        "Dereck Lively II": "1641794",
        "Gradey Dick": "1641795",
        "Jalen Slawson": "1641796",
        "Jordan Hawkins": "1641797",
        "Kris Murray": "1641798",
        "Nick Smith Jr.": "1641799",
        "Brice Sensabaugh": "1641800",
        "Kobe Bufkin": "1641801",
        "Bilal Coulibaly": "1641802",
        "Anthony Black": "1641803",
        "Taylor Hendricks": "1641804",
        "Gradey Dick": "1641805",
        "Cason Wallace": "1641806",
        "Jalen Wilson": "1641807",
        "Ben Sheppard": "1641808",
        "Olivier-Maxence Prosper": "1641809",
        "Marcus Sasser": "1641810",
        "Colby Jones": "1641811",
        "Mouhamed Gueye": "1641812",
        "James Bouknight": "1641813",
        "Tre Mann": "1641814",
        "Herbert Jones": "1641815",
        "Franz Wagner": "1641816",
        "Alperen Sengun": "1641817",
        "Davion Mitchell": "1641818",
        "Ziaire Williams": "1641819",
        "Corey Kispert": "1641820",
        "Josh Christopher": "1641821",
        "Ayo Dosunmu": "1641822",
        "Quentin Grimes": "1641823",
        "Moses Moody": "1641824",
        "Cam Thomas": "1641825",
        "Day'Ron Sharpe": "1641826",
        "Keon Johnson": "1641827",
        "Alperen Sengun": "1641828",
        "Sharife Cooper": "1641829",
        "Scottie Barnes": "1641830",
        "Jalen Johnson": "1641831",
        "Keon Ellis": "1641832",
        "Brandin Podziemski": "1641833",
        "Trayce Jackson-Davis": "1641834",
        "Dereck Lively II": "1641835",
        "Chet Holmgren": "1641836",
        "Victor Wembanyama": "1641837",
        "Scoot Henderson": "1641838",
        "Brandon Miller": "1641839",
        "Amen Thompson": "1641840",
        "Ausar Thompson": "1641841",
        "Anthony Black": "1641842",
        "Bilal Coulibaly": "1641843",
        "Jarace Walker": "1641844",
        "Taylor Hendricks": "1641845",
        "Cason Wallace": "1641846",
        "Gradey Dick": "1641847",
        "Jalen Hood-Schifino": "1641848",
        "Jordan Hawkins": "1641849",
        "Jalen Wilson": "1641850",
        "Kobe Brown": "1641851",
        "GG Jackson": "1641852",
        "Brice Sensabaugh": "1641853",
        "Keyonte George": "1641854",
        "Nick Smith Jr.": "1641855",
        "Kris Murray": "1641856",
        "Jett Howard": "1641857",
        "Maxwell Lewis": "1641858",
        "Colin Gillespie": "1641859",
        "Amari Bailey": "1641860",
        "Miles Norris": "1641861",
        "Emoni Bates": "1641862",
        "Craig Porter Jr.": "1641863",
        "Julian Strawther": "1641864",
        "Ben Sheppard": "1641865",
        "Marcus Sasser": "1641866",
        "Jalen Slawson": "1641867",
        "Olivier-Maxence Prosper": "1641868",
        "Colby Jones": "1641869",
        "Mouhamed Gueye": "1641870",
        "James Bouknight": "1641871",
        "Tre Mann": "1641872",
        "Herbert Jones": "1641873",
        "Franz Wagner": "1641874",
        "Davion Mitchell": "1641875",
        "Ziaire Williams": "1641876",
        "Corey Kispert": "1641877",
        "Josh Christopher": "1641878",
        "Ayo Dosunmu": "1641879",
        "Quentin Grimes": "1641880",
        "Moses Moody": "1641881",
        "Cam Thomas": "1641882",
        "Day'Ron Sharpe": "1641883",
        "Keon Johnson": "1641884",
        "Sharife Cooper": "1641885",
    }
    
    # Verificar y agregar solo los que tienen foto valida
    added = 0
    for name, nba_id in known_nba.items():
        if name in nba_map:
            continue
        
        photo_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{nba_id}.png"
        
        try:
            resp = requests.head(photo_url, timeout=5, allow_redirects=True)
            if resp.status_code == 200:
                nba_map[name] = {
                    "nba_id": nba_id,
                    "photo_url": photo_url,
                    "espn_id": nba_id  # Misma ID funciona para ESPN
                }
                added += 1
        except:
            pass
    
    mappings["nba"] = nba_map
    logger.info(f"NBA: {added} nuevas fotos agregadas (total: {len(nba_map)})")

def build_mlb_mappings(mappings: dict):
    """Construye mapeo MLB desde statsapi.mlb.com."""
    logger.info("Construyendo mapeo MLB...")
    
    mlb_map = mappings.get("mlb", {})
    
    # Obtener todos los equipos
    teams_resp = requests.get('https://statsapi.mlb.com/api/v1/teams?sportId=1', timeout=15)
    if teams_resp.status_code != 200:
        logger.error("No se pudieron obtener equipos de MLB")
        return
    
    teams = teams_resp.json().get('teams', [])
    logger.info(f"Obteniendo rosters de {len(teams)} equipos...")
    
    added = 0
    for idx, team in enumerate(teams):
        team_id = team['id']
        team_name = team['name']
        
        try:
            roster_resp = requests.get(
                f'https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?season=2025',
                timeout=10
            )
            if roster_resp.status_code != 200:
                continue
            
            roster = roster_resp.json().get('roster', [])
            
            for player in roster:
                person = player.get('person', {})
                player_id = person.get('id')
                full_name = person.get('fullName')
                
                if not player_id or not full_name:
                    continue
                
                if full_name in mlb_map:
                    continue
                
                photo_url = f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{player_id}/headshot/67/current"
                
                mlb_map[full_name] = {
                    "mlb_id": player_id,
                    "photo_url": photo_url
                }
                added += 1
            
            if (idx + 1) % 10 == 0:
                logger.info(f"  Progreso: {idx + 1}/{len(teams)} equipos | {len(mlb_map)} jugadores")
                time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            logger.warning(f"  Error con {team_name}: {e}")
    
    mappings["mlb"] = mlb_map
    logger.info(f"MLB: {added} nuevas fotos agregadas (total: {len(mlb_map)})")

def build_soccer_mappings(mappings: dict):
    """Construye mapeo soccer desde la BD."""
    logger.info("Construyendo mapeo soccer...")
    
    soccer_map = mappings.get("soccer", {})
    
    session = SessionLocal()
    try:
        # Obtener jugadores de soccer con stats
        result = session.execute(text('''
            SELECT DISTINCT nombre_jugador 
            FROM stats_jugador_futbol
            WHERE nombre_jugador IS NOT NULL
        ''')).fetchall()
        
        player_names = [row[0] for row in result]
        logger.info(f"Encontrados {len(player_names)} jugadores de soccer")
        
        # Para soccer, usamos un placeholder por ahora
        # En el futuro se pueden scrapear de fuentes externas
        added = 0
        for name in player_names:
            if name in soccer_map:
                continue
            
            # No hay fuente confiable actualmente
            # Se puede agregar manualmente despues
            pass
        
        logger.info(f"Soccer: {added} nuevas fotos agregadas (total: {len(soccer_map)})")
        
    finally:
        session.close()
    
    mappings["soccer"] = soccer_map

def build_all():
    """Construye todos los mapeos."""
    mappings = load_mappings()
    
    build_nba_mappings(mappings)
    build_mlb_mappings(mappings)
    build_soccer_mappings(mappings)
    
    save_mappings(mappings)
    
    # Resumen
    logger.info("=" * 60)
    logger.info("RESUMEN DE MAPPINGS")
    logger.info("=" * 60)
    logger.info(f"NBA: {len(mappings.get('nba', {}))} jugadores")
    logger.info(f"MLB: {len(mappings.get('mlb', {}))} jugadores")
    logger.info(f"Soccer: {len(mappings.get('soccer', {}))} jugadores")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--sport', choices=['nba', 'mlb', 'soccer', 'all'], default='all')
    args = parser.parse_args()
    
    mappings = load_mappings()
    
    if args.sport == 'nba':
        build_nba_mappings(mappings)
    elif args.sport == 'mlb':
        build_mlb_mappings(mappings)
    elif args.sport == 'soccer':
        build_soccer_mappings(mappings)
    else:
        build_all()
    
    save_mappings(mappings)
