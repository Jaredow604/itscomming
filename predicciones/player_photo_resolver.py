"""
player_photo_resolver.py — Resuelve fotos de jugadores.

Estrategia:
1. Cache local (BD)
2. Photo mappings (photo_mappings.json)
3. Soccer: usa avatar fallback (no hay fuente confiable actualmente)
"""

import logging
import requests
import json
from pathlib import Path
from database import SessionLocal
from sqlalchemy import text

logger = logging.getLogger(__name__)

PHOTO_MAPPINGS_FILE = Path(__file__).parent.parent / "photo_mappings.json"

CACHE = {}

def load_photo_mappings() -> dict:
    """Carga mapeos de fotos desde JSON."""
    if PHOTO_MAPPINGS_FILE.exists():
        try:
            with open(PHOTO_MAPPINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"nba": {}, "mlb": {}, "soccer": {}}

def resolve_player_photo(player_name: str, team_name: str, sport: str) -> str:
    """Resuelve la foto de un jugador."""
    cache_key = f"{sport}:{player_name}:{team_name}"

    if cache_key in CACHE:
        return CACHE[cache_key]

    # 1. Buscar en cache BD
    cached_url = _get_cached_url(player_name)
    if cached_url:
        CACHE[cache_key] = cached_url
        return cached_url

    # 2. Buscar en photo mappings
    mappings = load_photo_mappings()
    sport_map = mappings.get(sport, {})
    
    if player_name in sport_map:
        photo_url = sport_map[player_name].get("photo_url", "")
        if photo_url:
            # No verificar URL para evitar latencia - confiar en mappings
            _save_cached_url(player_name, photo_url)
            CACHE[cache_key] = photo_url
            return photo_url

    CACHE[cache_key] = ""
    return ""


def bulk_resolve_photos(players: list[dict], sport: str) -> list[dict]:
    """Resuelve fotos para multiples jugadores."""
    mappings = load_photo_mappings()
    sport_map = mappings.get(sport, {})
    
    for player in players:
        if player.get("photo_url"):
            continue
        
        name = player["name"]
        
        # Buscar en mappings
        if name in sport_map:
            photo_url = sport_map[name].get("photo_url", "")
            if photo_url:
                player["photo_url"] = photo_url
                continue
    
    return players


def _verify_url(url: str) -> bool:
    """Verifica que la URL existe."""
    try:
        resp = requests.head(url, timeout=5, allow_redirects=True)
        return resp.status_code == 200
    except Exception:
        return False


def _get_cached_url(player_name: str) -> str | None:
    """Busca photo_url cacheada en la BD."""
    try:
        session = SessionLocal()
        try:
            query = text("""
                SELECT photo_url FROM ml_inference_ready_player_data
                WHERE player_name = :name AND photo_url IS NOT NULL AND photo_url != ''
                ORDER BY created_at DESC LIMIT 1
            """)
            result = session.execute(query, {"name": player_name}).fetchone()
            if result and result[0]:
                return result[0]
        finally:
            session.close()
    except Exception:
        pass
    return None


def _save_cached_url(player_name: str, photo_url: str) -> None:
    """Guarda photo_url en la BD."""
    try:
        session = SessionLocal()
        try:
            session.execute(text("""
                UPDATE ml_inference_ready_player_data
                SET photo_url = :url
                WHERE player_name = :name
            """), {"url": photo_url, "name": player_name})
            session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"Failed to cache photo_url for {player_name}: {e}")
