import random
import time
import logging
import requests
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class RequestManager:
    """
    Gestor de peticiones Anti-Ban enfocado a operaciones ofensivas de Web Scraping.
    Implementa tiempos de espera uniformes e inyección de agentes de usuario simulados.
    """
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
    ]

    def __init__(self, use_proxies: bool = False):
        """
        Inicializa el RequestManager.
        
        Args:
            use_proxies (bool): Flag para activar rotación de proxies (para futura integración).
        """
        self.session = requests.Session()
        self.use_proxies = use_proxies
        # Aquí se montarían routers de proxy dinámicos si fuera necesario.

    def _get_random_headers(self) -> Dict[str, str]:
        """Genera cabeceras creíbles rotando User-Agents aleatorios."""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    def _throttle(self):
        """Aplica un retraso semialeatorio para evadir mecanismos rate-limit (HTTP 429)."""
        sleep_time = random.uniform(1.5, 3.5)
        logger.debug(f"Pausa de seguridad anti-ban: {sleep_time:.2f} segundos...")
        time.sleep(sleep_time)

    def get(self, url: str) -> Optional[requests.Response]:
        """
        Realiza una petición GET segura.
        
        Args:
            url (str): Dominio destino.
            
        Returns:
            Optional[requests.Response]: Objeto de respuesta o None si falla.
        """
        self._throttle()
        headers = self._get_random_headers()
        
        try:
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            logger.info(f"[200 OK] Extracción exitosa desde {url}")
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[ERROR {getattr(e.response, 'status_code', 'N/A')}] Falla de red en {url}: {e}")
            return None
