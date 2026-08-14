import os
import glob
import re
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from safetensors.torch import save_file, load_file
import importlib.util
from multiprocessing import Pool, cpu_count

# Dynamically import the HuggingFace encoder (csi-embed-v2.py)
spec = importlib.util.spec_from_file_location("csi_embed", "csi-embed-v2.py")
csi_embed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csi_embed)
Enc = csi_embed.Enc

# ==============================================================================
# Signal Processing (Same as our main feature extractor)
# ==============================================================================
from scipy.signal import butter, filtfilt, savgol_filter

def remove_dc(signal):
    return signal - np.mean(signal)

def butter_bandpass_filter(data, lowcut=0.1, highcut=3.0, fs=20.0, order=3):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut/nyq, highcut/nyq], btype='band')
    return filtfilt(b, a, data)

def savitzky_golay_smooth(data, window_size=15, poly_order=3):
    if len(data) < window_size:
        return data
    return savgol_filter(data, window_size, poly_order)

def calculate_amplitude(csi_str):
    if pd.isna(csi_str): return 0.0
    try:
        csi_str = csi_str.strip("[]")
        arr = np.fromstring(csi_str, sep=' ')
        if len(arr) == 0:
            arr = np.fromstring(csi_str, sep=',')
        if len(arr) != 128: return 0.0
        real, imag = arr[::2], arr[1::2]
        return float(np.mean(np.sqrt(real**2 + imag**2)))
    except:
        return 0.0

def process_single_file(args):
    f, window_size = args
    basename = os.path.basename(f)
    match = re.search(r'Subject (\d+)\.csv', basename)
    if not match: return [], []
    
    subject_id = int(match.group(1)) - 1
    print(f"Processing Identity: {basename} -> Class {subject_id}")
    
    try:
        df = pd.read_csv(f, nrows=15000)
    except Exception as e:
        print(f"Error reading {f}: {e}")
        return [], []
    
    amps = []
    # Check for CSI_DATA string vs SC_0..SC_63 expansion
    if 'CSI_DATA' in df.columns:
        amps = df['CSI_DATA'].apply(calculate_amplitude).values
    elif 'SC_0' in df.columns:
        sc_cols = [f'SC_{i}' for i in range(64) if f'SC_{i}' in df.columns]
        df_sc = df[sc_cols].astype(str)
        row_strings = df_sc.apply(lambda row: ','.join(row.values), axis=1)
        
        def fast_parse(s):
            nums = [float(x) for x in re.findall(r'[-+]?\d*\.\d+|\d+', s)]
            if not nums: return 0.0
            if len(nums) % 2 != 0: nums.append(0.0)
            mags = [np.sqrt(nums[j]**2 + nums[j+1]**2) for j in range(0, len(nums), 2)]
            return np.mean(mags) if mags else 0.0
            
        amps = row_strings.apply(fast_parse).values
    else:
        return [], []
    
    local_features = []
    local_labels = []
    for i in range(0, len(amps) - window_size, window_size // 2):
        window = amps[i:i+window_size]
        dc_removed = remove_dc(window)
        bandpassed = butter_bandpass_filter(dc_removed, fs=100.0)
        shaped = savitzky_golay_smooth(bandpassed)
        
        feat = np.array([
            np.mean(shaped), np.std(shaped), np.max(shaped), np.min(shaped), 
            np.median(shaped), np.percentile(shaped, 25), np.percentile(shaped, 75), np.var(shaped)
        ], dtype=np.float32)
        
        local_features.append(feat)
        local_labels.append(subject_id)
        
    return local_features, local_labels

# ==============================================================================
# Identity Dataset
# ==============================================================================
class IdentityDataset(Dataset):
    def __init__(self, data_dir, window_size=100):
        self.features = []
        self.labels = []
        
        # Load only Subject 1 and Subject 2
        csv_files = [
            os.path.join(data_dir, "Subject 1.csv"),
            os.path.join(data_dir, "Subject 2.csv")
        ]
        csv_files = [f for f in csv_files if os.path.exists(f)]
        print(f"Found {len(csv_files)} subject identity files. Using {cpu_count()} CPU cores...")
        
        args = [(f, window_size) for f in csv_files]
        with Pool(processes=min(cpu_count(), len(csv_files))) as pool:
            results = pool.map(process_single_file, args)
            
        for local_features, local_labels in results:
            self.features.extend(local_features)
            self.labels.extend(local_labels)
                
        self.features = np.array(self.features)
        self.labels = np.array(self.labels, dtype=np.int64)
        print(f"Total extracted identity samples: {len(self.features)}")

    def __len__(self):
        return len(self.features)
    
    def __getitem__(self, idx):
        feat = self.features[idx].copy()
        
        # Identity augmentation (to make it robust to slight room changes)
        scale = np.random.uniform(0.9, 1.1)
        feat *= scale
            
        return torch.tensor(feat, dtype=torch.float32), self.labels[idx]

# ==============================================================================
# Classifier Head
# ==============================================================================
class IdentityHead(nn.Module):
    def __init__(self, num_classes=2):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, num_classes)
        )
        
    def forward(self, embeddings):
        return self.fc(embeddings)

# ==============================================================================
# Training Script
# ==============================================================================
def train():
    data_dir = r"d:\WeeCare\Dataset\CSI_Dataset"
    
    dataset = IdentityDataset(data_dir)
    loader = DataLoader(dataset, batch_size=128, shuffle=True)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")
    
    # 1. Load Pre-trained HuggingFace Encoder
    encoder = Enc().to(device)
    encoder.load_state_dict(load_file("csi-embed-v2.safetensors"), strict=True)
    encoder.eval() # We freeze the encoder!
    
    # 2. Init Head
    head = IdentityHead(num_classes=2).to(device)
    
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.005)
    criterion = nn.CrossEntropyLoss()
    
    epochs = 100
    print("Starting high-accuracy multi-person identity training (100 Epochs)...")
    
    for epoch in range(epochs):
        head.train()
        train_loss = 0
        correct = 0
        total = 0
        
        for batch_x, batch_y in loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            
            # Pass through frozen HF encoder to get 128-D fingerprints
            with torch.no_grad():
                embeddings = encoder(batch_x)
            
            optimizer.zero_grad()
            outputs = head(embeddings)
            loss = criterion(outputs, batch_y)
            
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += batch_y.size(0)
            correct += (predicted == batch_y).sum().item()
            
        acc = 100 * correct / total
        if (epoch + 1) % 5 == 0:
            print(f"Epoch [{epoch+1}/{epochs}] - Loss: {train_loss/len(loader):.4f} - Acc: {acc:.2f}%")
            
    print("Saving Identity Classifier Head...")
    save_file(head.state_dict(), "identity_head.safetensors")
    print("Exported identity_head.safetensors successfully!")

if __name__ == "__main__":
    train()
