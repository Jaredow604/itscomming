import logging
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import httpx

logger = logging.getLogger("Odds_Scraper_Playwright")

class OddsScraper:
    """
    Clase asíncrona avanzada para la extracción de cuotas de mercado (Odds).
    Implementa Scraping Ofensivo (Headless Playwright) y Pasivo (API 365Scores Backup).
    """
  
    def __init__(self):
        # Cabeceras limpias para el motor de backup
        self.headers_365 = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Origin": "https://www.365scores.com",
            "Referer": "https://www.365scores.com/",
        }

    async def get_market_odds(self, url: str, selector_target: str) -> dict:
        """
        Estrategia primaria (Playwright DOM Scraping): 
        Despliega una instancia headless, resuelve mitigaciones pasivas de bot-protection,
        extrae el payload del Document Object Model (DOM) contenedor. (ej: O/U 25.5 Pts) y las parsea.
        """
        logger.info(f"Inicializando worker Playwright (Chromium) URL:  {url}...")
        
        extracted_data = {}
        try:
            async with async_playwright() as p:
                # Launch parameters (Headless configurado para optimización de I/O de red)
                browser = await p.chromium.launch(headless=True)
                
                # Bypass heurístico en WAF (Randomized / Validated Context UA)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    java_script_enabled=True # Fundamental para dom dinámico (React/Angular)
                )
                
                page = await context.new_page()
                
                # Tolerancia networkidle configurada (Espera a resolución de callbacks asíncronos en Frontend)
                await page.goto(url, wait_until="networkidle", timeout=45000)
                
                # Promesa de WaitForSelector en nodos críticos
                await page.wait_for_selector(selector_target, timeout=15000)
                
                # Volcado del DOM subyacente del container resuelto a buffer local.
                html_content = await page.inner_html(selector_target)
                
                # Proceso de renderizado sintáctico (bs4 en in-memory DOM Tree)
                soup = BeautifulSoup(html_content, "html.parser")
                
                # Ejemplo de Extracción (Dependerá 100% del portal de apuestas a consumir):
                # options_blocks = soup.select(".odds-market-block .odds-button")
                # for block in options_blocks: 
                #     ...
                
                extracted_data["raw_scan"] = str(soup)[:300] # Primeros 300 bytes de prueba
                logger.info(" INFO: Fase Playwright scraping OK. Objeto DOM recuperado con éxito.")
                
                await browser.close()
                return extracted_data
                
        except Exception as e:
            logger.error(f"Error Crítico Timeout/TargetSelector no cumplido en headless scraping: : {e}")
            return {}

    async def get_odds_from_365scores(self, game_id: int) -> dict:
        """
        Mecanismo Fallback de Extracción Interna JSON: 
        Si WAF bloquea endpoints, el puente consume metadatos nativos desde API remota unificada 
        en nodo bestOdds de respuesta JSON pasiva.
        """
        logger.info(f"Fallback INFO: Recuperando nodo bestOdds para GameID: {game_id} vía Backbone...")
        
        endpoint = "https://webws.365scores.com/web/game/"
        params = {
            "appTypeId": 5, "langId": 27, "timezoneName": "America/Mexico_City",
            "userCountryId": 31, "bookmakerId": 4, "gameId": game_id
        }
        
        try:
            async with httpx.AsyncClient(http2=True) as client:
                res = await client.get(endpoint, params=params, headers=self.headers_365, timeout=15.0)
                res.raise_for_status()
                
                data = res.json()
                best_odds = data.get("game", {}).get("bestOdds", [])
                
                if not best_odds:
                    logger.warning(f"El nodo bestOdds no contiene mercados para ID {game_id}.")
                    return {}
                    
                lines_dict = {}
                for odd in best_odds:
                    lines_dict[odd.get('lineType', 'Unknown')] = {
                        "odds": odd.get("odds", 0.0),
                        "bookmaker_id": odd.get("bookmakerId", -1)
                    }
                    
                logger.info(f" INFO: Extracción JSON (Fallback API) exitosa. Mercados detectados: {list(lines_dict.keys())}")
                return lines_dict
                
        except httpx.HTTPError as he:
            logger.error(f"Falla de conexión en el Fallback Pasivo: {he}")
            return {}
        except Exception as e:
            logger.error(f"Error de Análisis de JSON: {e}")
            return {}
