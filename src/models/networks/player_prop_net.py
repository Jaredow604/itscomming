import torch
import torch.nn as nn

class PlayerPropNet(nn.Module):
    """
    Neural network architecture for predicting player performance (Player Props).
    Processes normalized features to output a raw prediction score.
    """
    def __init__(self, input_dim=3, hidden_dim=64, output_dim=1):
        super(PlayerPropNet, self).__init__()
        
        # Layer 1: Input to hidden layer
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        
        # Layer 2: Hidden layer to half hidden layer
        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        
        # Layer 3: Final output layer
        self.fc3 = nn.Linear(hidden_dim // 2, output_dim)
        
        # Activation function to break linearity
        self.relu = nn.ReLU()
        
        # Dropout layer to prevent overfitting
        self.dropout = nn.Dropout(p=0.2)

    def forward(self, x):
        """
        Defines the forward pass of the network.
        
        Args:
            x (torch.Tensor): Input tensor of features.
            
        Returns:
            torch.Tensor: Raw prediction score (no final activation).
        """
        # Pass through first layer, apply ReLU and Dropout
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout(x)
        
        # Pass through second layer, apply ReLU and Dropout
        x = self.fc2(x)
        x = self.relu(x)
        x = self.dropout(x)
        
        # Pass through output layer (no activation for regression as handled by loss function)
        x = self.fc3(x)
        
        return x

# Unit test block
if __name__ == "__main__":
    input_dim = 3
    
    # Instantiate the model
    model = PlayerPropNet(input_dim=input_dim)
    
    # Create a fake tensor simulating a single player's data (batch_size=1, features=3)
    dummy_input = torch.rand(1, input_dim)
    
    # Pass the tensor through the model
    raw_score = model(dummy_input)
    
    # Output the results
    print("--- Arquitectura de la Red Original (fc1, fc2, fc3) ---")
    print(model)
    print("\n--- Resultados de Prueba ---")
    print(f"Tensor de entrada: {dummy_input}")
    print(f"Raw Score (Predicción Cruda): {raw_score.item():.4f}")
