"""
update_logo_urls.py — Actualiza logo_url de equipos a CDN jsDelivr/GitHub.

1. Convierte rutas relativas (/media/logos/...) a URLs de jsDelivr CDN
2. Busca logos para equipos sin logo (usando ESPN API)
3. Mantiene URLs de ESPN existentes

Uso:
    python update_logo_urls.py
"""

import sys
import os
import logging
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import requests
from database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CDN_BASE = "https://cdn.jsdelivr.net/gh/Jaredow604/itscomming@main/logos/equipos/"

# Mapeo de nombres de equipos a nombres de archivo de logo
# Para equipos que no tienen archivo local pero sí existen en ESPN
ESPN_LOGO_MAP = {
    # NBA
    "Lakers": "https://a.espncdn.com/i/teamlogos/nba/500/lal.png",
    "Los Angeles Lakers": "https://a.espncdn.com/i/teamlogos/nba/500/lal.png",
    "Celtics": "https://a.espncdn.com/i/teamlogos/nba/500/bos.png",
    "Boston Celtics": "https://a.espncdn.com/i/teamlogos/nba/500/bos.png",
    "Warriors": "https://a.espncdn.com/i/teamlogos/nba/500/gs.png",
    "Golden State Warriors": "https://a.espncdn.com/i/teamlogos/nba/500/gs.png",
    "Bucks": "https://a.espncdn.com/i/teamlogos/nba/500/mil.png",
    "Milwaukee Bucks": "https://a.espncdn.com/i/teamlogos/nba/500/mil.png",
    "Nuggets": "https://a.espncdn.com/i/teamlogos/nba/500/den.png",
    "Denver Nuggets": "https://a.espncdn.com/i/teamlogos/nba/500/den.png",
    "Heat": "https://a.espncdn.com/i/teamlogos/nba/500/mia.png",
    "Miami Heat": "https://a.espncdn.com/i/teamlogos/nba/500/mia.png",
    "Suns": "https://a.espncdn.com/i/teamlogos/nba/500/phx.png",
    "Phoenix Suns": "https://a.espncdn.com/i/teamlogos/nba/500/phx.png",
    "76ers": "https://a.espncdn.com/i/teamlogos/nba/500/phi.png",
    "Philadelphia 76ers": "https://a.espncdn.com/i/teamlogos/nba/500/phi.png",
    "Knicks": "https://a.espncdn.com/i/teamlogos/nba/500/ny.png",
    "New York Knicks": "https://a.espncdn.com/i/teamlogos/nba/500/ny.png",
    "Clippers": "https://a.espncdn.com/i/teamlogos/nba/500/lac.png",
    "Los Angeles Clippers": "https://a.espncdn.com/i/teamlogos/nba/500/lac.png",
    "Mavericks": "https://a.espncdn.com/i/teamlogos/nba/500/dal.png",
    "Dallas Mavericks": "https://a.espncdn.com/i/teamlogos/nba/500/dal.png",
    "Thunder": "https://a.espncdn.com/i/teamlogos/nba/500/okc.png",
    "Oklahoma City Thunder": "https://a.espncdn.com/i/teamlogos/nba/500/okc.png",
    "Grizzlies": "https://a.espncdn.com/i/teamlogos/nba/500/mem.png",
    "Memphis Grizzlies": "https://a.espncdn.com/i/teamlogos/nba/500/mem.png",
    "Pelicans": "https://a.espncdn.com/i/teamlogos/nba/500/no.png",
    "New Orleans Pelicans": "https://a.espncdn.com/i/teamlogos/nba/500/no.png",
    "Spurs": "https://a.espncdn.com/i/teamlogos/nba/500/sa.png",
    "San Antonio Spurs": "https://a.espncdn.com/i/teamlogos/nba/500/sa.png",
    "Timberwolves": "https://a.espncdn.com/i/teamlogos/nba/500/min.png",
    "Minnesota Timberwolves": "https://a.espncdn.com/i/teamlogos/nba/500/min.png",
    "Kings": "https://a.espncdn.com/i/teamlogos/nba/500/sac.png",
    "Sacramento Kings": "https://a.espncdn.com/i/teamlogos/nba/500/sac.png",
    "Raptors": "https://a.espncdn.com/i/teamlogos/nba/500/tor.png",
    "Toronto Raptors": "https://a.espncdn.com/i/teamlogos/nba/500/tor.png",
    "Bulls": "https://a.espncdn.com/i/teamlogos/nba/500/chi.png",
    "Chicago Bulls": "https://a.espncdn.com/i/teamlogos/nba/500/chi.png",
    "Cavaliers": "https://a.espncdn.com/i/teamlogos/nba/500/cle.png",
    "Cleveland Cavaliers": "https://a.espncdn.com/i/teamlogos/nba/500/cle.png",
    "Pacers": "https://a.espncdn.com/i/teamlogos/nba/500/ind.png",
    "Indiana Pacers": "https://a.espncdn.com/i/teamlogos/nba/500/ind.png",
    "Hawks": "https://a.espncdn.com/i/teamlogos/nba/500/atl.png",
    "Atlanta Hawks": "https://a.espncdn.com/i/teamlogos/nba/500/atl.png",
    "Nets": "https://a.espncdn.com/i/teamlogos/nba/500/bkn.png",
    "Brooklyn Nets": "https://a.espncdn.com/i/teamlogos/nba/500/bkn.png",
    "Hornets": "https://a.espncdn.com/i/teamlogos/nba/500/cha.png",
    "Charlotte Hornets": "https://a.espncdn.com/i/teamlogos/nba/500/cha.png",
    "Pistons": "https://a.espncdn.com/i/teamlogos/nba/500/det.png",
    "Detroit Pistons": "https://a.espncdn.com/i/teamlogos/nba/500/det.png",
    "Magic": "https://a.espncdn.com/i/teamlogos/nba/500/orl.png",
    "Orlando Magic": "https://a.espncdn.com/i/teamlogos/nba/500/orl.png",
    "Wizards": "https://a.espncdn.com/i/teamlogos/nba/500/wsh.png",
    "Washington Wizards": "https://a.espncdn.com/i/teamlogos/nba/500/wsh.png",
    "Jazz": "https://a.espncdn.com/i/teamlogos/nba/500/utah.png",
    "Utah Jazz": "https://a.espncdn.com/i/teamlogos/nba/500/utah.png",
    "Trail Blazers": "https://a.espncdn.com/i/teamlogos/nba/500/por.png",
    "Portland Trail Blazers": "https://a.espncdn.com/i/teamlogos/nba/500/por.png",
    "Rockets": "https://a.espncdn.com/i/teamlogos/nba/500/hou.png",
    "Houston Rockets": "https://a.espncdn.com/i/teamlogos/nba/500/hou.png",
    
    # MLB
    "Yankees": "https://a.espncdn.com/i/teamlogos/mlb/500/nyy.png",
    "New York Yankees": "https://a.espncdn.com/i/teamlogos/mlb/500/nyy.png",
    "Red Sox": "https://a.espncdn.com/i/teamlogos/mlb/500/bos.png",
    "Boston Red Sox": "https://a.espncdn.com/i/teamlogos/mlb/500/bos.png",
    "Dodgers": "https://a.espncdn.com/i/teamlogos/mlb/500/lad.png",
    "Los Angeles Dodgers": "https://a.espncdn.com/i/teamlogos/mlb/500/lad.png",
    "Cubs": "https://a.espncdn.com/i/teamlogos/mlb/500/chc.png",
    "Chicago Cubs": "https://a.espncdn.com/i/teamlogos/mlb/500/chc.png",
    "Cardinals": "https://a.espncdn.com/i/teamlogos/mlb/500/stl.png",
    "St. Louis Cardinals": "https://a.espncdn.com/i/teamlogos/mlb/500/stl.png",
    "Astros": "https://a.espncdn.com/i/teamlogos/mlb/500/hou.png",
    "Houston Astros": "https://a.espncdn.com/i/teamlogos/mlb/500/hou.png",
    "Braves": "https://a.espncdn.com/i/teamlogos/mlb/500/atl.png",
    "Atlanta Braves": "https://a.espncdn.com/i/teamlogos/mlb/500/atl.png",
    "Mets": "https://a.espncdn.com/i/teamlogos/mlb/500/nym.png",
    "New York Mets": "https://a.espncdn.com/i/teamlogos/mlb/500/nym.png",
    "Phillies": "https://a.espncdn.com/i/teamlogos/mlb/500/phi.png",
    "Philadelphia Phillies": "https://a.espncdn.com/i/teamlogos/mlb/500/phi.png",
    "Giants": "https://a.espncdn.com/i/teamlogos/mlb/500/sf.png",
    "San Francisco Giants": "https://a.espncdn.com/i/teamlogos/mlb/500/sf.png",
    "Padres": "https://a.espncdn.com/i/teamlogos/mlb/500/sd.png",
    "San Diego Padres": "https://a.espncdn.com/i/teamlogos/mlb/500/sd.png",
    "Mariners": "https://a.espncdn.com/i/teamlogos/mlb/500/sea.png",
    "Seattle Mariners": "https://a.espncdn.com/i/teamlogos/mlb/500/sea.png",
    "Rangers": "https://a.espncdn.com/i/teamlogos/mlb/500/tex.png",
    "Texas Rangers": "https://a.espncdn.com/i/teamlogos/mlb/500/tex.png",
    "Angels": "https://a.espncdn.com/i/teamlogos/mlb/500/laa.png",
    "Los Angeles Angels": "https://a.espncdn.com/i/teamlogos/mlb/500/laa.png",
    "Athletics": "https://a.espncdn.com/i/teamlogos/mlb/500/oak.png",
    "Oakland Athletics": "https://a.espncdn.com/i/teamlogos/mlb/500/oak.png",
    "Rockies": "https://a.espncdn.com/i/teamlogos/mlb/500/col.png",
    "Colorado Rockies": "https://a.espncdn.com/i/teamlogos/mlb/500/col.png",
    "Diamondbacks": "https://a.espncdn.com/i/teamlogos/mlb/500/ari.png",
    "Arizona Diamondbacks": "https://a.espncdn.com/i/teamlogos/mlb/500/ari.png",
    "Marlins": "https://a.espncdn.com/i/teamlogos/mlb/500/mia.png",
    "Miami Marlins": "https://a.espncdn.com/i/teamlogos/mlb/500/mia.png",
    "Nationals": "https://a.espncdn.com/i/teamlogos/mlb/500/wsh.png",
    "Washington Nationals": "https://a.espncdn.com/i/teamlogos/mlb/500/wsh.png",
    "Pirates": "https://a.espncdn.com/i/teamlogos/mlb/500/pit.png",
    "Pittsburgh Pirates": "https://a.espncdn.com/i/teamlogos/mlb/500/pit.png",
    "Reds": "https://a.espncdn.com/i/teamlogos/mlb/500/cin.png",
    "Cincinnati Reds": "https://a.espncdn.com/i/teamlogos/mlb/500/cin.png",
    "Brewers": "https://a.espncdn.com/i/teamlogos/mlb/500/mil.png",
    "Milwaukee Brewers": "https://a.espncdn.com/i/teamlogos/mlb/500/mil.png",
    "Tigers": "https://a.espncdn.com/i/teamlogos/mlb/500/det.png",
    "Detroit Tigers": "https://a.espncdn.com/i/teamlogos/mlb/500/det.png",
    "Guardians": "https://a.espncdn.com/i/teamlogos/mlb/500/cle.png",
    "Cleveland Guardians": "https://a.espncdn.com/i/teamlogos/mlb/500/cle.png",
    "Royals": "https://a.espncdn.com/i/teamlogos/mlb/500/kc.png",
    "Kansas City Royals": "https://a.espncdn.com/i/teamlogos/mlb/500/kc.png",
    "Twins": "https://a.espncdn.com/i/teamlogos/mlb/500/min.png",
    "Minnesota Twins": "https://a.espncdn.com/i/teamlogos/mlb/500/min.png",
    "White Sox": "https://a.espncdn.com/i/teamlogos/mlb/500/chw.png",
    "Chicago White Sox": "https://a.espncdn.com/i/teamlogos/mlb/500/chw.png",
    "Indians": "https://a.espncdn.com/i/teamlogos/mlb/500/cle.png",
    "Cleveland Indians": "https://a.espncdn.com/i/teamlogos/mlb/500/cle.png",
    "Orioles": "https://a.espncdn.com/i/teamlogos/mlb/500/bal.png",
    "Baltimore Orioles": "https://a.espncdn.com/i/teamlogos/mlb/500/bal.png",
    "Rays": "https://a.espncdn.com/i/teamlogos/mlb/500/tb.png",
    "Tampa Bay Rays": "https://a.espncdn.com/i/teamlogos/mlb/500/tb.png",
    "Blue Jays": "https://a.espncdn.com/i/teamlogos/mlb/500/tor.png",
    "Toronto Blue Jays": "https://a.espncdn.com/i/teamlogos/mlb/500/tor.png",
    
    # Soccer (ESPN)
    "Real Madrid": "https://a.espncdn.com/i/teamlogos/soccer/500/86.png",
    "Barcelona": "https://a.espncdn.com/i/teamlogos/soccer/500/83.png",
    "Manchester United": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
    "Manchester City": "https://a.espncdn.com/i/teamlogos/soccer/500/281.png",
    "Liverpool": "https://a.espncdn.com/i/teamlogos/soccer/500/364.png",
    "Chelsea": "https://a.espncdn.com/i/teamlogos/soccer/500/363.png",
    "Arsenal": "https://a.espncdn.com/i/teamlogos/soccer/500/359.png",
    "Tottenham": "https://a.espncdn.com/i/teamlogos/soccer/500/367.png",
    "Tottenham Hotspur": "https://a.espncdn.com/i/teamlogos/soccer/500/367.png",
    "Newcastle United": "https://a.espncdn.com/i/teamlogos/soccer/500/361.png",
    "Aston Villa": "https://a.espncdn.com/i/teamlogos/soccer/500/362.png",
    "West Ham": "https://a.espncdn.com/i/teamlogos/soccer/500/371.png",
    "West Ham United": "https://a.espncdn.com/i/teamlogos/soccer/500/371.png",
    "Brighton": "https://a.espncdn.com/i/teamlogos/soccer/500/397.png",
    "Brighton & Hove Albion": "https://a.espncdn.com/i/teamlogos/soccer/500/397.png",
    "Wolves": "https://a.espncdn.com/i/teamlogos/soccer/500/380.png",
    "Wolverhampton Wanderers": "https://a.espncdn.com/i/teamlogos/soccer/500/380.png",
    "Everton": "https://a.espncdn.com/i/teamlogos/soccer/500/368.png",
    "Crystal Palace": "https://a.espncdn.com/i/teamlogos/soccer/500/384.png",
    "Fulham": "https://a.espncdn.com/i/teamlogos/soccer/500/370.png",
    "Brentford": "https://a.espncdn.com/i/teamlogos/soccer/500/402.png",
    "Nottingham Forest": "https://a.espncdn.com/i/teamlogos/soccer/500/365.png",
    "Bournemouth": "https://a.espncdn.com/i/teamlogos/soccer/500/349.png",
    "AFC Bournemouth": "https://a.espncdn.com/i/teamlogos/soccer/500/349.png",
    "Leicester City": "https://a.espncdn.com/i/teamlogos/soccer/500/369.png",
    "Leeds United": "https://a.espncdn.com/i/teamlogos/soccer/500/357.png",
    "Southampton": "https://a.espncdn.com/i/teamlogos/soccer/500/366.png",
    "Ipswich Town": "https://a.espncdn.com/i/teamlogos/soccer/500/356.png",
    "Atlético Madrid": "https://a.espncdn.com/i/teamlogos/soccer/500/1068.png",
    "Ath Bilbao": "https://a.espncdn.com/i/teamlogos/soccer/500/931.png",
    "Athletic Club": "https://a.espncdn.com/i/teamlogos/soccer/500/931.png",
    "Real Sociedad": "https://a.espncdn.com/i/teamlogos/soccer/500/1069.png",
    "Villarreal": "https://a.espncdn.com/i/teamlogos/soccer/500/1072.png",
    "Real Betis": "https://a.espncdn.com/i/teamlogos/soccer/500/1073.png",
    "Sevilla": "https://a.espncdn.com/i/teamlogos/soccer/500/1070.png",
    "Getafe": "https://a.espncdn.com/i/teamlogos/soccer/500/1074.png",
    "Celta Vigo": "https://a.espncdn.com/i/teamlogos/soccer/500/1071.png",
    "Valencia": "https://a.espncdn.com/i/teamlogos/soccer/500/1075.png",
    "Mallorca": "https://a.espncdn.com/i/teamlogos/soccer/500/1076.png",
    "Osasuna": "https://a.espncdn.com/i/teamlogos/soccer/500/1077.png",
    "Girona": "https://a.espncdn.com/i/teamlogos/soccer/500/1078.png",
    "Las Palmas": "https://a.espncdn.com/i/teamlogos/soccer/500/1079.png",
    "Rayo Vallecano": "https://a.espncdn.com/i/teamlogos/soccer/500/1080.png",
    "Leganes": "https://a.espncdn.com/i/teamlogos/soccer/500/1081.png",
    "Espanyol": "https://a.espncdn.com/i/teamlogos/soccer/500/1082.png",
    "Valladolid": "https://a.espncdn.com/i/teamlogos/soccer/500/1083.png",
    "Alaves": "https://a.espncdn.com/i/teamlogos/soccer/500/1084.png",
    "Alavés": "https://a.espncdn.com/i/teamlogos/soccer/500/1084.png",
    "Inter": "https://a.espncdn.com/i/teamlogos/soccer/500/1105.png",
    "Inter Milan": "https://a.espncdn.com/i/teamlogos/soccer/500/1105.png",
    "AC Milan": "https://a.espncdn.com/i/teamlogos/soccer/500/1106.png",
    "Juventus": "https://a.espncdn.com/i/teamlogos/soccer/500/1107.png",
    "Napoli": "https://a.espncdn.com/i/teamlogos/soccer/500/1108.png",
    "Roma": "https://a.espncdn.com/i/teamlogos/soccer/500/1109.png",
    "AS Roma": "https://a.espncdn.com/i/teamlogos/soccer/500/1109.png",
    "Lazio": "https://a.espncdn.com/i/teamlogos/soccer/500/1110.png",
    "Atalanta": "https://a.espncdn.com/i/teamlogos/soccer/500/1111.png",
    "Fiorentina": "https://a.espncdn.com/i/teamlogos/soccer/500/1112.png",
    "Bologna": "https://a.espncdn.com/i/teamlogos/soccer/500/1113.png",
    "Torino": "https://a.espncdn.com/i/teamlogos/soccer/500/1114.png",
    "Udinese": "https://a.espncdn.com/i/teamlogos/soccer/500/1115.png",
    "Monza": "https://a.espncdn.com/i/teamlogos/soccer/500/1116.png",
    "Empoli": "https://a.espncdn.com/i/teamlogos/soccer/500/1117.png",
    "Cagliari": "https://a.espncdn.com/i/teamlogos/soccer/500/1118.png",
    "Genoa": "https://a.espncdn.com/i/teamlogos/soccer/500/1119.png",
    "Lecce": "https://a.espncdn.com/i/teamlogos/soccer/500/1120.png",
    "Verona": "https://a.espncdn.com/i/teamlogos/soccer/500/1121.png",
    "Como": "https://a.espncdn.com/i/teamlogos/soccer/500/1122.png",
    "Parma": "https://a.espncdn.com/i/teamlogos/soccer/500/1123.png",
    "Bayern Munich": "https://a.espncdn.com/i/teamlogos/soccer/500/132.png",
    "Bayern": "https://a.espncdn.com/i/teamlogos/soccer/500/132.png",
    "Borussia Dortmund": "https://a.espncdn.com/i/teamlogos/soccer/500/131.png",
    "Dortmund": "https://a.espncdn.com/i/teamlogos/soccer/500/131.png",
    "RB Leipzig": "https://a.espncdn.com/i/teamlogos/soccer/500/23826.png",
    "Bayer Leverkusen": "https://a.espncdn.com/i/teamlogos/soccer/500/134.png",
    "Eintracht Frankfurt": "https://a.espncdn.com/i/teamlogos/soccer/500/135.png",
    "Freiburg": "https://a.espncdn.com/i/teamlogos/soccer/500/136.png",
    "Mainz": "https://a.espncdn.com/i/teamlogos/soccer/500/137.png",
    "Wolfsburg": "https://a.espncdn.com/i/teamlogos/soccer/500/138.png",
    "Hoffenheim": "https://a.espncdn.com/i/teamlogos/soccer/500/139.png",
    "Augsburg": "https://a.espncdn.com/i/teamlogos/soccer/500/140.png",
    "Werder Bremen": "https://a.espncdn.com/i/teamlogos/soccer/500/141.png",
    "Borussia M'gladbach": "https://a.espncdn.com/i/teamlogos/soccer/500/142.png",
    "Union Berlin": "https://a.espncdn.com/i/teamlogos/soccer/500/143.png",
    "1. FC Union Berlin": "https://a.espncdn.com/i/teamlogos/soccer/500/143.png",
    "Heidenheim": "https://a.espncdn.com/i/teamlogos/soccer/500/144.png",
    "1. FC Heidenheim 1846": "https://a.espncdn.com/i/teamlogos/soccer/500/144.png",
    "St. Pauli": "https://a.espncdn.com/i/teamlogos/soccer/500/145.png",
    "Holstein Kiel": "https://a.espncdn.com/i/teamlogos/soccer/500/146.png",
    "PSG": "https://a.espncdn.com/i/teamlogos/soccer/500/583.png",
    "Paris Saint-Germain": "https://a.espncdn.com/i/teamlogos/soccer/500/583.png",
    "Marseille": "https://a.espncdn.com/i/teamlogos/soccer/500/584.png",
    "Lyon": "https://a.espncdn.com/i/teamlogos/soccer/500/585.png",
    "Monaco": "https://a.espncdn.com/i/teamlogos/soccer/500/586.png",
    "AS Monaco": "https://a.espncdn.com/i/teamlogos/soccer/500/586.png",
    "Lille": "https://a.espncdn.com/i/teamlogos/soccer/500/587.png",
    "Nice": "https://a.espncdn.com/i/teamlogos/soccer/500/588.png",
    "Lens": "https://a.espncdn.com/i/teamlogos/soccer/500/589.png",
    "Rennes": "https://a.espncdn.com/i/teamlogos/soccer/500/590.png",
    "Strasbourg": "https://a.espncdn.com/i/teamlogos/soccer/500/591.png",
    "Toulouse": "https://a.espncdn.com/i/teamlogos/soccer/500/592.png",
    "Montpellier": "https://a.espncdn.com/i/teamlogos/soccer/500/593.png",
    "Nantes": "https://a.espncdn.com/i/teamlogos/soccer/500/594.png",
    "Reims": "https://a.espncdn.com/i/teamlogos/soccer/500/595.png",
    "Brest": "https://a.espncdn.com/i/teamlogos/soccer/500/596.png",
    "Auxerre": "https://a.espncdn.com/i/teamlogos/soccer/500/597.png",
    "AJ Auxerre": "https://a.espncdn.com/i/teamlogos/soccer/500/597.png",
    "Angers": "https://a.espncdn.com/i/teamlogos/soccer/500/598.png",
    "Le Havre": "https://a.espncdn.com/i/teamlogos/soccer/500/599.png",
    "Saint-Etienne": "https://a.espncdn.com/i/teamlogos/soccer/500/600.png",
    "Club América": "https://a.espncdn.com/i/teamlogos/soccer/500/2282.png",
    "América": "https://a.espncdn.com/i/teamlogos/soccer/500/2282.png",
    "Chivas": "https://a.espncdn.com/i/teamlogos/soccer/500/2283.png",
    "Guadalajara": "https://a.espncdn.com/i/teamlogos/soccer/500/2283.png",
    "Cruz Azul": "https://a.espncdn.com/i/teamlogos/soccer/500/2284.png",
    "Tigres": "https://a.espncdn.com/i/teamlogos/soccer/500/2285.png",
    "Monterrey": "https://a.espncdn.com/i/teamlogos/soccer/500/2286.png",
    "Santos Laguna": "https://a.espncdn.com/i/teamlogos/soccer/500/2287.png",
    "Pumas": "https://a.espncdn.com/i/teamlogos/soccer/500/2288.png",
    "UNAM": "https://a.espncdn.com/i/teamlogos/soccer/500/2288.png",
    "Toluca": "https://a.espncdn.com/i/teamlogos/soccer/500/2289.png",
    "Leon": "https://a.espncdn.com/i/teamlogos/soccer/500/2290.png",
    "Atlas": "https://a.espncdn.com/i/teamlogos/soccer/500/2291.png",
    "Pachuca": "https://a.espncdn.com/i/teamlogos/soccer/500/2292.png",
    "Puebla": "https://a.espncdn.com/i/teamlogos/soccer/500/2293.png",
    "Querétaro": "https://a.espncdn.com/i/teamlogos/soccer/500/2294.png",
    "Necaxa": "https://a.espncdn.com/i/teamlogos/soccer/500/2295.png",
    "Mazatlán": "https://a.espncdn.com/i/teamlogos/soccer/500/2296.png",
    "Atlético de San Luis": "https://a.espncdn.com/i/teamlogos/soccer/500/2297.png",
    "Juárez": "https://a.espncdn.com/i/teamlogos/soccer/500/2298.png",
    # Variaciones de nombres
    "Manchester Utd": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
    "Man United": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
    "Man Utd": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
    "Inter": "https://a.espncdn.com/i/teamlogos/soccer/500/1105.png",
    "Inter Milan": "https://a.espncdn.com/i/teamlogos/soccer/500/1105.png",
    "AC Milan": "https://a.espncdn.com/i/teamlogos/soccer/500/1106.png",
    "Roma": "https://a.espncdn.com/i/teamlogos/soccer/500/1109.png",
    "AS Roma": "https://a.espncdn.com/i/teamlogos/soccer/500/1109.png",
    "Ipswich": "https://a.espncdn.com/i/teamlogos/soccer/500/356.png",
    "Ipswich Town": "https://a.espncdn.com/i/teamlogos/soccer/500/356.png",
    "Luton": "https://a.espncdn.com/i/teamlogos/soccer/500/358.png",
    "Luton Town": "https://a.espncdn.com/i/teamlogos/soccer/500/358.png",
    "Leicester": "https://a.espncdn.com/i/teamlogos/soccer/500/369.png",
    "Leicester City": "https://a.espncdn.com/i/teamlogos/soccer/500/369.png",
    "Sheffield United": "https://a.espncdn.com/i/teamlogos/soccer/500/355.png",
    "Bochum": "https://a.espncdn.com/i/teamlogos/soccer/500/147.png",
    "Darmstadt": "https://a.espncdn.com/i/teamlogos/soccer/500/148.png",
    "Cadiz": "https://a.espncdn.com/i/teamlogos/soccer/500/1085.png",
    "Cádiz": "https://a.espncdn.com/i/teamlogos/soccer/500/1085.png",
    "Granada": "https://a.espncdn.com/i/teamlogos/soccer/500/1086.png",
    "Frosinone": "https://a.espncdn.com/i/teamlogos/soccer/500/1124.png",
    "Clermont": "https://a.espncdn.com/i/teamlogos/soccer/500/601.png",
    "Salernitana": "https://a.espncdn.com/i/teamlogos/soccer/500/1125.png",
    # Equipos que ya deberían estar cubiertos pero por si acaso
    "Bayer Leverkusen": "https://a.espncdn.com/i/teamlogos/soccer/500/134.png",
    "Borussia Dortmund": "https://a.espncdn.com/i/teamlogos/soccer/500/131.png",
    "Los Angeles Clippers": "https://a.espncdn.com/i/teamlogos/nba/500/lac.png",
    "Leicester City": "https://a.espncdn.com/i/teamlogos/soccer/500/369.png",
    "Holstein Kiel": "https://a.espncdn.com/i/teamlogos/soccer/500/146.png",
    "Southampton": "https://a.espncdn.com/i/teamlogos/soccer/500/366.png",
    "Montpellier": "https://a.espncdn.com/i/teamlogos/soccer/500/593.png",
    "Reims": "https://a.espncdn.com/i/teamlogos/soccer/500/595.png",
    "Empoli": "https://a.espncdn.com/i/teamlogos/soccer/500/1117.png",
    "Monza": "https://a.espncdn.com/i/teamlogos/soccer/500/1116.png",
    "Las Palmas": "https://a.espncdn.com/i/teamlogos/soccer/500/1079.png",
    "Valladolid": "https://a.espncdn.com/i/teamlogos/soccer/500/1083.png",
    "Leganes": "https://a.espncdn.com/i/teamlogos/soccer/500/1081.png",
    "Leganés": "https://a.espncdn.com/i/teamlogos/soccer/500/1081.png",
}

def update_relative_urls(session):
    """Convierte rutas relativas a URLs de jsDelivr CDN."""
    logger.info("Actualizando rutas relativas a jsDelivr CDN...")
    
    result = session.execute(text("""
        SELECT id_equipo, nombre, logo_url 
        FROM equipos 
        WHERE logo_url LIKE '/media/logos/equipos/%'
    """)).fetchall()
    
    updated = 0
    not_found = 0
    
    for row in result:
        equipo_id, nombre, logo_url = row
        filename = logo_url.split('/')[-1]
        
        # Verificar que el archivo existe en logos/equipos/
        local_path = project_root / "logos" / "equipos" / filename
        if local_path.exists():
            new_url = CDN_BASE + filename
            session.execute(text("""
                UPDATE equipos SET logo_url = :url WHERE id_equipo = :id
            """), {"url": new_url, "id": equipo_id})
            updated += 1
        else:
            not_found += 1
            logger.warning(f"  Archivo no encontrado: {filename} ({nombre})")
    
    session.commit()
    logger.info(f"  Actualizados: {updated} | No encontrados: {not_found}")
    return updated

def update_missing_logos(session):
    """Busca logos para equipos sin logo usando ESPN API o archivos locales."""
    logger.info("Buscando logos para equipos sin logo...")
    
    result = session.execute(text("""
        SELECT id_equipo, nombre 
        FROM equipos 
        WHERE logo_url IS NULL OR logo_url = ''
    """)).fetchall()
    
    updated = 0
    
    for row in result:
        equipo_id, nombre = row
        
        # 1. Buscar en el mapeo de ESPN
        espn_url = ESPN_LOGO_MAP.get(nombre)
        
        if espn_url:
            # Verificar que la URL funciona
            try:
                resp = requests.head(espn_url, timeout=5, allow_redirects=True)
                if resp.status_code == 200:
                    session.execute(text("""
                        UPDATE equipos SET logo_url = :url WHERE id_equipo = :id
                    """), {"url": espn_url, "id": equipo_id})
                    updated += 1
                    logger.info(f"  {nombre}: ESPN {espn_url[:60]}...")
                    continue
            except:
                pass
        
        # 2. Buscar archivo local en logos/equipos/
        # Mapeo de nombres a archivos locales
        local_files = {
            "AS Roma": "as_roma.png",
            "Inter Milan": "inter.png",
            "AC Milan": "ac_milan.png",
            "Roma": "roma.png",
            "Milan": "milan.png",
            "Internazionale": "internazionale.png",
        }
        
        filename = local_files.get(nombre)
        if filename:
            local_path = project_root / "logos" / "equipos" / filename
            if local_path.exists():
                new_url = CDN_BASE + filename
                session.execute(text("""
                    UPDATE equipos SET logo_url = :url WHERE id_equipo = :id
                """), {"url": new_url, "id": equipo_id})
                updated += 1
                logger.info(f"  {nombre}: Local {filename}")
                continue
        
        # 3. Intentar buscar por variaciones del nombre
        # Para equipos españoles/italianos que podrían tener acentos
        nombre_clean = nombre.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        
        for espn_name, espn_url in ESPN_LOGO_MAP.items():
            if espn_name.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u') == nombre_clean:
                try:
                    resp = requests.head(espn_url, timeout=5, allow_redirects=True)
                    if resp.status_code == 200:
                        session.execute(text("""
                            UPDATE equipos SET logo_url = :url WHERE id_equipo = :id
                        """), {"url": espn_url, "id": equipo_id})
                        updated += 1
                        logger.info(f"  {nombre}: ESPN (variación) {espn_url[:60]}...")
                        break
                except:
                    pass
    
    session.commit()
    logger.info(f"  Logos encontrados para: {updated} equipos")
    return updated

def main():
    logger.info("=" * 60)
    logger.info("Actualizando logo_urls a CDN jsDelivr/GitHub")
    logger.info("=" * 60)
    
    session = SessionLocal()
    try:
        # 1. Actualizar rutas relativas
        rel_updated = update_relative_urls(session)
        
        # 2. Buscar logos para equipos sin logo
        missing_updated = update_missing_logos(session)
        
        # Resumen
        logger.info("=" * 60)
        logger.info("RESUMEN")
        logger.info("=" * 60)
        logger.info(f"Rutas relativas actualizadas: {rel_updated}")
        logger.info(f"Logos encontrados para equipos sin logo: {missing_updated}")
        
    finally:
        session.close()

if __name__ == "__main__":
    main()
