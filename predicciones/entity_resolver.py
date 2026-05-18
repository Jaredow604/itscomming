import re
import unicodedata
from rapidfuzz import fuzz, process
from .models import Equipos, AliasEquipo, EntidadHuerfana

# Diccionario de palabras comodín globales, prefijos y sufijos a remover
STOP_WORDS = {
    'fc', 'cf', 'afc', 'sad', 'real', 'deportivo', 'athletic', 'club', 'balompie', 'calcio',
    'united', 'city', 'rovers', 'wanderers', 'hotspur', 'sporting', 'internazionale', 'milano',
    'cd', 'sc', 'ac', 'as', 'ud', 'rc', 'sociedad', 'b', '1', '05', '04', 'sv', 'fsv', 'tsv'
}

def clean_team_name(name: str) -> str:
    """
    Función de limpieza base avanzada para estandarizar strings de nombres de equipos.
    """
    if not name:
        return ""
        
    # 1. Convertir a minúsculas
    name = name.lower()
    
    # 2. Eliminar acentos y diéresis
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    
    # 3. Eliminar signos de puntuación (reemplazar con espacio para separar palabras)
    name = re.sub(r'[^\w\s]', ' ', name)
    
    # 4. Eliminar espacios múltiples
    name = re.sub(r'\s+', ' ', name).strip()
    
    # 5. Remover palabras comodín
    words = name.split()
    cleaned_words = [w for w in words if w not in STOP_WORDS]
    
    # Si al limpiar nos quedamos sin palabras (ej. un equipo que literalmente se llamaba 'Club FC'),
    # devolvemos el string limpio pero con las stopwords para tener algo con lo que comparar.
    if not cleaned_words:
        return name
        
    return ' '.join(cleaned_words)


def resolver_entidad_equipo(nombre_crudo: str, umbral_fuzzy: int = 85):
    """
    Flujo principal de Entity Resolution para mapear nombre_crudo a un objeto Equipo.
    """
    if not nombre_crudo:
        return None

    # Paso A: Búsqueda rápida en la tabla de Alias (coincidencia exacta)
    alias = AliasEquipo.objects.filter(nombre_fuente__iexact=nombre_crudo).first()
    if alias:
        return alias.equipo
        
    # Paso B: Aplicar limpieza base y buscar coincidencia exacta contra DB
    nombre_limpio = clean_team_name(nombre_crudo)
    equipos = list(Equipos.objects.all())
    
    for equipo in equipos:
        equipo_limpio = clean_team_name(equipo.nombre)
        if equipo_limpio == nombre_limpio:
            # Encontramos match exacto post-limpieza. Lo guardamos como alias para acelerar la próxima vez.
            AliasEquipo.objects.get_or_create(nombre_fuente=nombre_crudo, equipo=equipo)
            return equipo
            
    # Paso C: Fuzzy Matching Inteligente con RapidFuzz
    # Creamos un diccionario con el id del equipo y su nombre limpio
    choices = {e.id: clean_team_name(e.nombre) for e in equipos}
    
    # extractOne devuelve una tupla: (texto_coincidente, puntuacion, clave_diccionario)
    match = process.extractOne(
        nombre_limpio, 
        choices, 
        scorer=fuzz.token_sort_ratio,
        score_cutoff=umbral_fuzzy
    )
    
    if match:
        _, score, equipo_id = match
        equipo = Equipos.objects.get(id=equipo_id)
        # Lo guardamos en Alias para que en el futuro pase por el Paso A
        AliasEquipo.objects.get_or_create(nombre_fuente=nombre_crudo, equipo=equipo)
        return equipo
        
    # Paso D: Si todo falla, registrar en EntidadHuerfana
    EntidadHuerfana.objects.get_or_create(nombre_crudo=nombre_crudo)
    return None
