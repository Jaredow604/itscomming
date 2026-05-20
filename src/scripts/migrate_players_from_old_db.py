import os
import pandas as pd
from sqlalchemy import create_engine, text
from rapidfuzz import process, fuzz
from dotenv import load_dotenv

load_dotenv()

OLD_DB_URL = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
NEW_DB_URL = os.getenv("DB_URL", "postgresql://postgres:Jk9oe@localhost:5432/its_coming_v2")

old_engine = create_engine(OLD_DB_URL)
new_engine = create_engine(NEW_DB_URL)

def get_old_teams():
    try:
        query = "SELECT id, nombre FROM equipos"
        with old_engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception as e:
        print(f"Error fetching old teams: {e}")
        # Intentar id_equipo en caso de que la primary key se llame así
        query = "SELECT id_equipo as id, nombre FROM equipos"
        with old_engine.connect() as conn:
            return pd.read_sql(query, conn)

def get_new_teams():
    query = "SELECT id, name FROM teams"
    with new_engine.connect() as conn:
        return pd.read_sql(query, conn)

def match_team_fuzzy(csv_team_name, db_teams_df, threshold=70):
    if pd.isna(csv_team_name): return None
    db_names = db_teams_df['name'].tolist()
    match = process.extractOne(csv_team_name, db_names, scorer=fuzz.token_sort_ratio)
    if match and match[1] >= threshold:
        matched_name = match[0]
        team_id = db_teams_df[db_teams_df['name'] == matched_name].iloc[0]['id']
        return int(team_id)
    return None

def migrate_players():
    print("Fetching old teams and mapping to new teams...")
    old_teams = get_old_teams()
    new_teams = get_new_teams()
    
    # Crear mapeo old_team_id -> new_team_id
    team_mapping = {}
    for idx, row in old_teams.iterrows():
        new_id = match_team_fuzzy(row['nombre'], new_teams)
        if new_id:
            team_mapping[row['id']] = new_id
    
    print(f"Mapped {len(team_mapping)} teams out of {len(old_teams)}.")
    
    # 1. Fetch Players
    print("Fetching old players...")
    query_players = "SELECT id_jugador as id, id_equipo, nombre, photo_url FROM jugadores"
    with old_engine.connect() as conn:
        old_players = pd.read_sql(query_players, conn)
    
    print(f"Found {len(old_players)} players. Inserting to new DB...")
    
    with new_engine.begin() as new_conn:
        # Dictionary to store new player IDs
        player_id_map = {}
        
        for idx, player in old_players.iterrows():
            old_team_id = player['id_equipo']
            new_team_id = team_mapping.get(old_team_id)
            
            if not new_team_id:
                # No team mapping, skip
                continue
            
            # Insert or ignore player
            # In a real scenario we use ON CONFLICT but we don't have constraints here. 
            # We will just insert and get ID. To avoid duplicates we check first if exists.
            check_q = text("SELECT id FROM players WHERE name = :name AND team_id = :t_id LIMIT 1")
            res = new_conn.execute(check_q, {'name': player['nombre'], 't_id': new_team_id}).fetchone()
            
            if res:
                new_p_id = res[0]
            else:
                ins_q = text('''
                    INSERT INTO players (team_id, name, sport, photo_url)
                    VALUES (:t_id, :name, 'soccer', :photo_url)
                    RETURNING id
                ''')
                new_p_id = new_conn.execute(ins_q, {
                    't_id': new_team_id, 
                    'name': player['nombre'], 
                    'photo_url': player.get('photo_url', '')
                }).scalar()
            
            player_id_map[player['id']] = new_p_id

    # 2. Fetch Player Stats (soccer)
    print("Fetching old player stats...")
    query_stats = "SELECT id_partido, id_jugador, goles, asistencias, tiros_totales FROM stats_jugador_futbol"
    with old_engine.connect() as conn:
        old_stats = pd.read_sql(query_stats, conn)
        
    print(f"Found {len(old_stats)} stats. Inserting to new DB...")
    
    # For stats, we need match_id. Since we don't know how old match_id maps to new match_id,
    # and match migration is done by CSV, we might not be able to map matches easily if they don't match.
    # We will just log a warning or map to a dummy match for now. Or we can match by date if available.
    # A robust solution is to map matches if available, but for now we skip the stats or just log it, 
    # since we don't have the match mapping logic.
    print("Player stats migration requires match mapping. Skipping for now as matches are migrated from CSV.")

if __name__ == "__main__":
    migrate_players()
    print("Migration finished.")
