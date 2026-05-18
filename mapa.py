import os

# Carpetas basura que no aportan valor a la arquitectura
IGNORAR = {'venv', 'node_modules', '.git', '__pycache__', '.idea', 'build', 'dist'}

def generar_arbol(ruta, nivel=0):
    elementos = sorted(os.listdir(ruta))
    for i, elemento in enumerate(elementos):
        if elemento in IGNORAR:
            continue
            
        ruta_completa = os.path.join(ruta, elemento)
        es_ultimo = (i == len(elementos) - 1)
        prefijo = "└── " if es_ultimo else "├── "
        
        print("    " * nivel + prefijo + elemento)
        
        if os.path.isdir(ruta_completa):
            generar_arbol(ruta_completa, nivel + 1)

print("Estructura de It's Coming:")
print("==========================")
generar_arbol('.')