import torch
import torch.nn as nn
import os
import django

# 1. Configuración de Django para acceder a los datos
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from predicciones.models import Equipos

# 2. Debemos tener la MISMA estructura de la red que usamos para entrenar
class FootballOracleNet(nn.Module):
    def __init__(self, num_features):
        super(FootballOracleNet, self).__init__()
        self.capa1 = nn.Linear(num_features, 16)
        self.activacion1 = nn.ReLU()
        self.capa2 = nn.Linear(16, 8)
        self.activacion2 = nn.ReLU()
        self.salida = nn.Linear(8, 3)

    def forward(self, x):
        x = self.activacion1(self.capa1(x))
        x = self.activacion2(self.capa2(x))
        x = self.salida(x)
        return x

def testear_ia():
    # Cargar el modelo
    modelo = FootballOracleNet(num_features=2)
    modelo.load_state_dict(torch.load('oracle_brain.pth'))
    modelo.eval() # Modo evaluación (apaga el aprendizaje)

    print("🤖 IA 'It's Coming' Lista para inferencia.")
    
    # --- PRUEBA MANUAL ---
    # Vamos a simular un partido: Local promedia 2.5 goles, Visita promedia 0.8
    test_input = torch.FloatTensor([[2.5, 0.8]]) 
    
    with torch.no_grad(): # No calculamos gradientes para probar
        salida_cruda = modelo(test_input)
        # Aplicamos Softmax para convertir la salida de la red en probabilidades (0 a 1)
        probabilidades = torch.nn.functional.softmax(salida_cruda, dim=1)
    
    probs = probabilidades[0].tolist()
    # Recordar nuestro orden: 0: Empate, 1: Local, 2: Visita
    print(f"\n📊 Resultado del Test (Local 2.5 vs Visita 0.8):")
    print(f"🏠 Victoria Local: {probs[1]*100:.2f}%")
    print(f"🤝 Empate:         {probs[0]*100:.2f}%")
    print(f"Probabilidad Visita: {probs[2]*100:.2f}%")

if __name__ == '__main__':
    testear_ia()