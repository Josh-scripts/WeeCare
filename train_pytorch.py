import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import time
class VitalSignsNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm1 = nn.LSTM(input_size=1, hidden_size=64, batch_first=True)
        self.drop1 = nn.Dropout(0.2)
        self.lstm2 = nn.LSTM(input_size=64, hidden_size=32, batch_first=True)
        self.drop2 = nn.Dropout(0.2)
        self.fc1 = nn.Linear(32, 16)
        self.fc2 = nn.Linear(16, 2)

    def forward(self, x):
        x, _ = self.lstm1(x)
        x = self.drop1(x)
        x, _ = self.lstm2(x)
        x = x[:, -1, :]
        x = self.drop2(x)
        x = torch.relu(self.fc1(x))
        return self.fc2(x)

def generate_synthetic_data(num_samples=10000, seq_len=100, fs=100.0):
    print(f"Generating {num_samples} synthetic patient records...")
    X = np.zeros((num_samples, seq_len, 1), dtype=np.float32)
    Y = np.zeros((num_samples, 2), dtype=np.float32) # [HeartRate, BreathingRate]
    
    t = np.arange(seq_len) / fs
    
    for i in range(num_samples):
        # Ground truth BPMs
        hr_bpm = np.random.uniform(50.0, 100.0)
        br_bpm = np.random.uniform(10.0, 25.0)
        
        # Convert to Hz
        hr_hz = hr_bpm / 60.0
        br_hz = br_bpm / 60.0
        
        # Base signal: Breathing is dominant, heart rate is a micro-ripple
        breathing_wave = 1.0 * np.sin(2 * np.pi * br_hz * t)
        heart_wave = 0.2 * np.sin(2 * np.pi * hr_hz * t)
        
        # Add static Wi-Fi noise and DC offset
        noise = np.random.normal(0, 0.3, size=seq_len)
        dc_offset = np.random.uniform(30.0, 60.0)
        
        signal = dc_offset + breathing_wave + heart_wave + noise
        
        X[i, :, 0] = signal
        Y[i, 0] = hr_bpm
        Y[i, 1] = br_bpm
        
    return torch.from_numpy(X), torch.from_numpy(Y)

def train_model():
    # 1. Setup Model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")
    
    model = VitalSignsNet().to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.005)
    criterion = nn.MSELoss()
    
    # 2. Generate Data
    X_train, Y_train = generate_synthetic_data(num_samples=15000)
    X_val, Y_val = generate_synthetic_data(num_samples=2000)
    
    dataset = torch.utils.data.TensorDataset(X_train, Y_train)
    loader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=True)
    
    epochs = 40
    print("Beginning LSTM Training...")
    
    start_time = time.time()
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        
        for batch_x, batch_y in loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            preds = model(batch_x)
            loss = criterion(preds, batch_y)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        avg_loss = total_loss / len(loader)
        
        # Validation
        model.eval()
        with torch.no_grad():
            val_preds = model(X_val.to(device))
            val_loss = criterion(val_preds, Y_val.to(device)).item()
            
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"Epoch [{epoch+1}/{epochs}] - Train MSE: {avg_loss:.2f} | Val MSE: {val_loss:.2f}")
            
    print(f"Training Complete in {time.time() - start_time:.1f} seconds!")
    
    # Save Model Weights
    torch.save(model.state_dict(), "csi_hr.pth")
    print("Saved trained brain to 'csi_hr.pth'!")

if __name__ == "__main__":
    train_model()
