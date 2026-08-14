import os
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from safetensors.torch import save_file
import glob
import re

# ==============================================================================
# Model Definition (Must match main.py)
# ==============================================================================
class VitalSignsNet(nn.Module):
    def __init__(self):
        super(VitalSignsNet, self).__init__()
        self.encoder = nn.Sequential(
            nn.BatchNorm1d(8),  # Global feature normalization
            nn.Linear(8, 64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU()
        )
        self.head_hr = nn.Linear(64, 1)
        self.head_br = nn.Linear(64, 1)
        
    def forward(self, x):
        features = self.encoder(x)
        hr = self.head_hr(features)
        br = self.head_br(features)
        return {"heartbeat_rate": hr, "breathing_rate": br}

# ==============================================================================
# Signal Processing (Must match main.py)
# ==============================================================================
from scipy.signal import butter, filtfilt, savgol_filter

def remove_dc(signal):
    return signal - np.mean(signal)

def butter_bandpass_filter(data, lowcut=0.1, highcut=3.0, fs=20.0, order=3):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data)

def savitzky_golay_smooth(data, window_size=15, poly_order=3):
    if len(data) < window_size:
        return data
    return savgol_filter(data, window_size, poly_order)

def calculate_amplitude(csi_str):
    if pd.isna(csi_str):
        return 0.0
    try:
        csi_str = csi_str.strip("[]")
        arr = np.fromstring(csi_str, sep=' ')
        if len(arr) == 0:
            arr = np.fromstring(csi_str, sep=',')
        if len(arr) != 128:
            return 0.0
        
        real = arr[::2]
        imag = arr[1::2]
        amps = np.sqrt(real**2 + imag**2)
        return float(np.mean(amps))
    except:
        return 0.0

# ==============================================================================
# PyTorch Dataset
# ==============================================================================
class VitalSignsDataset(Dataset):
    def __init__(self, data_pairs, window_size=100, transform=False):
        self.features = []
        self.targets = []
        self.transform = transform
        
        for csi_file, label_file, target_br in data_pairs:
            print(f"Processing CSI: {os.path.basename(csi_file)} -> Target BR: {target_br}")
            df_csi = pd.read_csv(csi_file)
            
            # Handle labels
            if label_file and os.path.exists(label_file):
                df_labels = pd.read_csv(label_file)
                if 'Arb1' in df_labels.columns:
                    df_labels = df_labels.dropna(subset=['Arb1'])
                    hr_labels = df_labels['Arb1'].values
                else:
                    hr_labels = np.full(len(df_csi), 70.0) 
            else:
                # Fallback if no label file provided (e.g. Validity dataset)
                hr_labels = np.full(len(df_csi), 70.0)
            
            df_csi['amp'] = df_csi['CSI_DATA'].apply(calculate_amplitude)
            amps = df_csi['amp'].values
            
            for i in range(0, len(amps) - window_size, window_size // 2):
                window = amps[i:i+window_size]
                
                # Signal Processing
                dc_removed = remove_dc(window)
                bandpassed = butter_bandpass_filter(dc_removed, fs=100.0) 
                shaped = savitzky_golay_smooth(bandpassed)
                
                # 8D Features
                feat = np.array([
                    np.mean(shaped), np.std(shaped), np.max(shaped), np.min(shaped), 
                    np.median(shaped), np.percentile(shaped, 25), np.percentile(shaped, 75), np.var(shaped)
                ], dtype=np.float32)
                
                lbl_idx = min(len(hr_labels) - 1, i // 2)
                hr = hr_labels[lbl_idx]
                
                if hr < 40 or hr > 150:
                    continue
                    
                target = np.array([hr, target_br], dtype=np.float32)
                
                self.features.append(feat)
                self.targets.append(target)
                
        self.features = np.array(self.features)
        self.targets = np.array(self.targets)
        print(f"Total extracted samples across all files: {len(self.features)}")

    def __len__(self):
        return len(self.features)
    
    def __getitem__(self, idx):
        feat = self.features[idx].copy()
        target = self.targets[idx].copy()
        
        # Apply Data Augmentation
        if self.transform:
            # 1. Random noise injection
            noise = np.random.normal(0, 0.1, size=feat.shape)
            feat += noise
            
            # 2. Random feature scaling 
            scale = np.random.uniform(0.7, 1.3)
            feat *= scale
            
        return torch.tensor(feat, dtype=torch.float32), torch.tensor(target, dtype=torch.float32)

# ==============================================================================
# Training Loop
# ==============================================================================
def train():
    vital_dir = r"d:\WeeCare\Dataset\Sleep Disturbances Dataset\Vital Signs"
    data_pairs = [
        (os.path.join(vital_dir, "Breathing - 12 BPM - CSI.csv"), 
         os.path.join(vital_dir, "Breathing - Belt & HR.csv"), 
         12.0)
    ]
    
    # Add Validity datasets (12 BPM to 28 BPM)
    validity_dir = r"d:\WeeCare\Dataset\Respiration Rate Measurement Validity and Repeatability of Ubiquitous Non-contact Wi-Fi Sensing for Older Adults in Care\Validity\Wi-Fi Sensor RR"
    
    if os.path.exists(validity_dir):
        val_files = glob.glob(os.path.join(validity_dir, "Val-*BPM.csv"))
        for f in val_files:
            basename = os.path.basename(f)
            match = re.search(r'Val-(\d+)BPM\.csv', basename)
            if match:
                br_target = float(match.group(1))
                data_pairs.append((f, None, br_target))
                
    print(f"Found {len(data_pairs)} dataset pairs to train on!")
    print("Loading datasets and extracting features (this might take a minute)...")
    
    train_dataset = VitalSignsDataset(data_pairs, transform=True)
    train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")
    
    model = VitalSignsNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    criterion = nn.MSELoss()
    
    epochs = 100
    print("Starting robust ACCURATE training...")
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        
        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            preds = model(batch_x)
            
            loss_hr = criterion(preds["heartbeat_rate"].squeeze(), batch_y[:, 0])
            loss_br = criterion(preds["breathing_rate"].squeeze(), batch_y[:, 1])
            # Weight breathing rate loss heavier since it's the primary varying feature we want to learn now
            loss = (0.2 * loss_hr) + (1.0 * loss_br)
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            
            train_loss += loss.item()
            
        train_loss /= len(train_loader)
        
        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{epochs}] - Train Loss: {train_loss:.4f}")
            
    # Save the model
    print("Training complete! Saving weights to model.safetensors...")
    save_file(model.state_dict(), "model.safetensors")
    print("Exported successfully.")

if __name__ == "__main__":
    train()
