import os
import pandas as pd
from sqlalchemy import create_engine, text
from rapidfuzz import process, fuzz
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DB_URL", "postgresql://postgres:Jk9oe@localhost:5432/its_coming_v2")
engine = create_engine(DB_URL)

def get_db_teams():
    query = "SELECT id, name FROM teams"
    with engine.connect() as conn:
        return pd.read_sql(query, conn)

def match_team_fuzzy(csv_team_name, db_teams_df, threshold=80):
    db_names = db_teams_df['name'].tolist()
    match = process.extractOne(csv_team_name, db_names, scorer=fuzz.token_sort_ratio)
    if match and match[1] >= threshold:
        matched_name = match[0]
        team_id = db_teams_df[db_teams_df['name'] == matched_name].iloc[0]['id']
        return int(team_id)
    return None

def process_csv(file_path):
    df = pd.read_csv(file_path)
    db_teams = get_db_teams()
    
    with engine.begin() as conn:
        for idx, row in df.iterrows():
            # Búsqueda y Cruce
            home_team_id = match_team_fuzzy(row['HomeTeam'], db_teams)
            away_team_id = match_team_fuzzy(row['AwayTeam'], db_teams)
            
            if not home_team_id or not away_team_id:
                print(f"Skipping row {idx}: Could not match teams {row['HomeTeam']} or {row['AwayTeam']}")
                continue
                
            match_date = pd.to_datetime(row['Date']).date()
            
            # Inserción Relacional (Matches) - ON CONFLICT
            match_query = text('''
                INSERT INTO matches (home_team_id, away_team_id, match_date, home_score, away_score, status)
                VALUES (:home_id, :away_id, :m_date, :h_score, :a_score, 'FINISHED')
                ON CONFLICT (home_team_id, away_team_id, match_date) DO UPDATE SET 
                    home_score = EXCLUDED.home_score, 
                    away_score = EXCLUDED.away_score
                RETURNING id;
            ''')
            
            result = conn.execute(match_query, {
                'home_id': home_team_id, 
                'away_id': away_team_id, 
                'm_date': match_date,
                'h_score': row.get('FTHG', 0),
                'a_score': row.get('FTAG', 0)
            })
            match_id = result.scalar()
            
            # Inserción Relacional (Soccer Match Stats)
            stat_query = text('''
                INSERT INTO soccer_match_stats (match_id, team_id, is_home, xg)
                VALUES (:m_id, :t_id, :is_h, :xg)
                ON CONFLICT (match_id, team_id) DO NOTHING;
            ''')
            
            conn.execute(stat_query, {
                'm_id': match_id, 't_id': home_team_id, 'is_h': True, 'xg': row.get('Home_xG', 0.0)
            })
            conn.execute(stat_query, {
                'm_id': match_id, 't_id': away_team_id, 'is_h': False, 'xg': row.get('Away_xG', 0.0)
            })

if __name__ == "__main__":
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    for file in csv_files:
        print(f"Processing {file}...")
        try:
            process_csv(os.path.join(data_dir, file))
        except Exception as e:
            print(f"Failed to process {file}: {e}")
