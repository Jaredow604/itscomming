import json
import logging
import pandas as pd
from bs4 import BeautifulSoup
from typing import Dict, Any, List
from .request_manager import RequestManager

logger = logging.getLogger(__name__)

class StatsScraper:
    """
    Módulo 1: Scraper Estadístico.
    Especializado en extracciones estructurales (BeautifulSoup) de históricos y métricas xG.
    """
    def __init__(self):
        self.req_manager = RequestManager()

    def scrape_xg_data(self, match_url: str) -> Dict[str, Any]:
        """
        Interroga páginas en búsqueda de estructuras JSON incrustadas en el DOM
        asociadas a estadísticas avanzadas que un modelo PyTorch procesará.
        
        Args:
            match_url (str): Enlace directo del portal de estadísticas.
            
        Returns:
            Dict[str, Any]: Diccionario listo para UPSERT en PostgreSQL.
        """
        logger.info(f"Iniciando extracción de xG para: {match_url}")
        res = self.req_manager.get(match_url)
        
        if not res:
            logger.warning("Abortando scrape_xg_data debido a fallo de red.")
            return {"status": "error", "data": None}

        soup = BeautifulSoup(res.content, "html.parser")
        extracted_data = {}

        try:
            # Lógica Ofensiva: Localizar scripts inline que los frontends (ej. React) inyectan
            script_tags = soup.find_all('script')
            
            for script in script_tags:
                content = script.string
                if content and "matchData" in content:
                    # Parseo de fuerza bruta JSON en strings truncados
                    start_idx = content.find("JSON.parse('") + 12
                    end_idx = content.find("')", start_idx)
                    
                    if start_idx > 11 and end_idx != -1:
                        raw_json = content[start_idx:end_idx]
                        raw_json = raw_json.encode('utf-8').decode('unicode_escape')
                        json_data = json.loads(raw_json)
                        
                        # Extraer métricas clave (xG local y visitante)
                        extracted_data["home_xG"] = json_data.get("home", {}).get("expected_goals", 0.0)
                        extracted_data["away_xG"] = json_data.get("away", {}).get("expected_goals", 0.0)
                        extracted_data["possession_danger"] = json_data.get("possession_zones", [])
                        break
                        
        except json.JSONDecodeError as e:
            logger.error(f"Falla crítica: Estructura JSON ofuscada o cambiada: {e}")
        except Exception as e:
            # Excepción Defensiva: El scraper debe morir suavemente sin tumbar la canalización
            logger.error(f"Selector no encontrado o DOM mutado en {match_url}: {e}")

        # Normalizamos con Pandas antes de exportar
        df = pd.DataFrame([extracted_data])
        logger.info(f"Métricas normalizadas a Dataframe -> Filas: {len(df)}")
        
        return {
            "status": "success",
            "source": "stats_processor",
            "metrics": extracted_data
        }
