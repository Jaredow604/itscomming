import torch
import torch.nn as nn

class MatchPredictionNet(nn.Module):
    """
    Neural network architecture for Match Prediction (Moneyline - 1X2).
    Processes 6 continuous variables representing Head-to-Head & Team synergies.
    """
    def __init__(self, input_dim=6, hidden_dim=64, output_dim=3):
        super(MatchPredictionNet, self).__init__()
        
        # Estructura profunda encadenada en un nn.Sequential
        # input_dim -> 64 -> Dropout -> 32 -> Salida(3 clases: Empate, Local, Visita)
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim // 2, output_dim)
        )

    def forward(self, x):
        """
        Produce logits de probabilidad para las 3 clases de Moneyline.
        (El target está manejado con CrossEntropyLoss que implícitamente aplica Softmax).
        """
        return self.network(x)

if __name__ == "__main__":
    # Test Block
    input_dim = 6
    model = MatchPredictionNet(input_dim=input_dim)
    
    # Simular una tanda de datos (1 partido, 6 features)
    dummy_input = torch.rand(1, input_dim)
    output_logits = model(dummy_input)
    
    # Calcular Softmax sólo para visualizar cómo lo leerá la UI
    probs = torch.nn.functional.softmax(output_logits, dim=1)
    
    print("--- Arquitectura MatchPredictionNet (H2H) ---")
    print(model)
    print("\n--- Simulación ---")
    print(f"Features: {dummy_input}")
    print(f"Logits crudos: {output_logits}")
    print(f"Probabilidades [Empate(0), Local(1), Visita(2)]: {probs}")
