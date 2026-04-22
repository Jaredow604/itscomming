import httpx
import json

# Usamos uno de los GameIDs de la NBA que tu scraper atrapó antes
game_id = 4526099 
url = f"https://webws.365scores.com/web/game/?appTypeId=5&langId=29&timezoneName=America%2FMexico_City&userCountryId=31&gameId={game_id}"

print(f"Haciendo petición a: {url}")
response = httpx.get(url)

if response.status_code == 200:
    data = response.json()
    print("\n=== LLAVES PRINCIPALES DEL JSON ===")
    print(data.keys())
    
    if 'game' in data:
        print("\n=== LLAVES DENTRO DE 'game' ===")
        print(data['game'].keys())
        
        # Vamos a ver si el scraper estaba buscando en el lugar correcto
        if 'statistics' in data['game']:
            print("\nLas estadísticas están en game['statistics']")
            # En diccionarios anidados por equipo
            print("\nEstructura de estadísticas validada por equipo.")
        else:
            print("\n❌ Las estadísticas NO están donde el agente pensaba.")
            # Imprimimos un pedazo del JSON para ver dónde se esconden
            print("\nFragmento del juego para analizar:")
            print(json.dumps(data['game'], indent=2)[:500]) 
else:
    print(f"Error en la petición: {response.status_code}")