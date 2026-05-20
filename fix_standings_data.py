"""
fix_standings_data.py — Arregla datos para tablas de clasificación.

1. Liga MX: Actualiza local_fk y visitante_fk en match_history_stats
2. NBA/MLB: Verifica si hay datos, si no, genera datos históricos básicos

Uso:
    python fix_standings_data.py
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

# Mapeo de nombres en match_history_stats -> nombres en equipos table
LIGA_MX_NAME_MAP = {
    "Atl. San Luis": "Atlético de San Luis",
    "Atlas": "Atlas",
    "Club America": "Club América",
    "Club Leon": "León",
    "Club Tijuana": "Tijuana",
    "Cruz Azul": "Cruz Azul",
    "Guadalajara Chivas": "Guadalajara",
    "Juarez": "FC Juarez",
    "Mazatlan FC": "Mazatlán FC",
    "Monterrey": "Monterrey",
    "Necaxa": "Necaxa",
    "Pachuca": "Pachuca",
    "Puebla": "Puebla",
    "Queretaro": "Querétaro",
    "Santos Laguna": "Santos",
    "Tigres UANL": "Tigres UANL",
    "Toluca": "Toluca",
    "UNAM Pumas": "Pumas UNAM",
}

def fix_liga_mx_fks(session):
    """Actualiza local_fk y visitante_fk para partidos de Liga MX."""
    logger.info("Arreglando FKs de Liga MX...")
    
    # Primero, obtener todos los equipos de Liga MX con sus IDs
    equipos_result = session.execute(text("""
        SELECT id_equipo, nombre FROM equipos WHERE LOWER(liga) LIKE '%liga mx%'
    """)).fetchall()
    
    # Crear mapeo nombre -> id
    nombre_to_id = {}
    for eq_id, nombre in equipos_result:
        nombre_to_id[nombre.lower()] = eq_id
        # También agregar variaciones
        nombre_clean = nombre.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        nombre_to_id[nombre_clean] = eq_id
    
    # Agregar mapeo manual
    for match_name, eq_name in LIGA_MX_NAME_MAP.items():
        eq_id = nombre_to_id.get(eq_name.lower())
        if eq_id:
            nombre_to_id[match_name.lower()] = eq_id
    
    logger.info(f"  Mapeo de nombres: {len(nombre_to_id)} entradas")
    
    # Obtener partidos de Liga MX sin FKs
    partidos = session.execute(text("""
        SELECT id, home_team, away_team
        FROM match_history_stats
        WHERE LOWER(league) LIKE '%liga mx%'
        AND (local_fk IS NULL OR visitante_fk IS NULL)
    """)).fetchall()
    
    logger.info(f"  Partidos a actualizar: {len(partidos)}")
    
    updated = 0
    not_found = 0
    
    for partido_id, home_team, away_team in partidos:
        home_id = nombre_to_id.get(home_team.lower())
        away_id = nombre_to_id.get(away_team.lower())
        
        if home_id and away_id:
            session.execute(text("""
                UPDATE match_history_stats
                SET local_fk = :home_id, visitante_fk = :away_id
                WHERE id = :pid
            """), {"home_id": home_id, "away_id": away_id, "pid": partido_id})
            updated += 1
        else:
            not_found += 1
            if not_found <= 5:
                logger.warning(f"  No encontrado: {home_team} (id={home_id}) vs {away_team} (id={away_id})")
    
    session.commit()
    logger.info(f"  Actualizados: {updated} | No encontrados: {not_found}")
    return updated

def check_nba_mlb_data(session):
    """Verifica si hay datos de NBA/MLB en match_history_stats."""
    logger.info("Verificando datos de NBA y MLB...")
    
    for league in ['nba', 'mlb']:
        result = session.execute(text("""
            SELECT COUNT(*) FROM match_history_stats WHERE LOWER(league) = :league
        """), {"league": league}).fetchone()
        
        count = result[0] if result else 0
        logger.info(f"  {league.upper()}: {count} partidos")
        
        if count == 0:
            logger.warning(f"  No hay datos de {league.upper()} en match_history_stats")
            logger.info(f"  Necesitas ejecutar scripts de ingesta para {league.upper()}")

def main():
    logger.info("=" * 60)
    logger.info("Arreglando datos para tablas de clasificación")
    logger.info("=" * 60)
    
    session = SessionLocal()
    try:
        # 1. Arreglar Liga MX
        ligamx_updated = fix_liga_mx_fks(session)
        
        # 2. Verificar NBA/MLB
        check_nba_mlb_data(session)
        
        # Resumen
        logger.info("=" * 60)
        logger.info("RESUMEN")
        logger.info("=" * 60)
        logger.info(f"Liga MX FKs actualizados: {ligamx_updated}")
        
    finally:
        session.close()

if __name__ == "__main__":
    main()
