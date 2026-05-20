"""
add_missing_ligamx_teams.py — Agrega equipos faltantes de Liga MX a la tabla equipos.

Equipos en match_history_stats pero no en equipos:
- Club América
- León
- Mazatlán FC
- Querétaro
- Atlético de San Luis

Uso:
    python add_missing_ligamx_teams.py
"""

import sys
import os
import logging
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Equipos faltantes con sus datos
MISSING_TEAMS = [
    {"nombre": "Club América", "liga": "Liga MX", "logo_url": "https://a.espncdn.com/i/teamlogos/soccer/500/2282.png"},
    {"nombre": "León", "liga": "Liga MX", "logo_url": "https://a.espncdn.com/i/teamlogos/soccer/500/2290.png"},
    {"nombre": "Mazatlán FC", "liga": "Liga MX", "logo_url": "https://a.espncdn.com/i/teamlogos/soccer/500/2296.png"},
    {"nombre": "Querétaro", "liga": "Liga MX", "logo_url": "https://a.espncdn.com/i/teamlogos/soccer/500/2294.png"},
    {"nombre": "Atlético de San Luis", "liga": "Liga MX", "logo_url": "https://a.espncdn.com/i/teamlogos/soccer/500/2297.png"},
]

def add_missing_teams(session):
    """Agrega equipos faltantes a la tabla equipos."""
    logger.info("Agregando equipos faltantes de Liga MX...")
    
    # Obtener el max id_equipo actual
    max_id_result = session.execute(text("SELECT MAX(id_equipo) FROM equipos")).fetchone()
    next_id = (max_id_result[0] or 0) + 1
    
    added = 0
    for team in MISSING_TEAMS:
        # Verificar si ya existe
        existing = session.execute(text("""
            SELECT id_equipo FROM equipos WHERE LOWER(nombre) = LOWER(:nombre)
        """), {"nombre": team["nombre"]}).fetchone()
        
        if existing:
            logger.info(f"  {team['nombre']} ya existe (id={existing[0]})")
            continue
        
        # Insertar nuevo equipo con ID manual
        team["id_equipo"] = next_id
        session.execute(text("""
            INSERT INTO equipos (id_equipo, nombre, liga, logo_url)
            VALUES (:id_equipo, :nombre, :liga, :logo_url)
        """), team)
        
        next_id += 1
        added += 1
        logger.info(f"  Agregado: {team['nombre']} (id={team['id_equipo']})")
    
    session.commit()
    logger.info(f"  Equipos agregados: {added}")
    return added

def main():
    logger.info("=" * 60)
    logger.info("Agregando equipos faltantes de Liga MX")
    logger.info("=" * 60)
    
    session = SessionLocal()
    try:
        added = add_missing_teams(session)
        
        logger.info("=" * 60)
        logger.info("RESUMEN")
        logger.info("=" * 60)
        logger.info(f"Equipos agregados: {added}")
        
    finally:
        session.close()

if __name__ == "__main__":
    main()
