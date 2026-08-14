import os
import glob
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler

class CSIDataset(Dataset):
    """
    PyTorch Dataset for Wi-Fi Channel State Information (CSI) multivariate time-series sequences.
    """
    def __init__(self, sequences, labels, transform=None):
        self.sequences = torch.from_numpy(sequences).float() # Shape: (N, C, L)
        self.labels = torch.from_numpy(labels).long()        # Shape: (N,)
        self.transform = transform

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        x = self.sequences[idx]
        y = self.labels[idx]
        if self.transform:
            x = self.transform(x)
        return x, y

def apply_augmentation(sequence):
    """
    Data augmentation for CSI subcarrier sequences:
    1. Random Gaussian noise injection
    2. Subcarrier scaling jittering
    """
    noise = torch.randn_like(sequence) * 0.02
    scaled = sequence * (0.95 + 0.1 * torch.rand(sequence.shape[0], 1))
    return scaled + noise

def parse_csi_array(df, subcarrier_cols):
    """
    Converts DataFrame subcarrier columns to float32 matrix, handling float values
    as well as complex string representations '[real, imag]'.
    """
    raw_vals = df[subcarrier_cols].values
    num_rows, num_cols = raw_vals.shape
    out_matrix = np.zeros((num_rows, num_cols), dtype=np.float32)
    
    # Check if first row contains strings
    is_string_col = [isinstance(raw_vals[0, j], str) for j in range(num_cols)]
    
    for j in range(num_cols):
        col_data = raw_vals[:, j]
        if is_string_col[j]:
            parsed = np.zeros(num_rows, dtype=np.float32)
            for i in range(num_rows):
                val = col_data[i]
                if isinstance(val, str):
                    val = val.strip()
                    if val.startswith('[') and val.endswith(']'):
                        parts = val[1:-1].split(',')
                        if len(parts) == 2:
                            try:
                                r, img = float(parts[0]), float(parts[1])
                                parsed[i] = np.sqrt(r*r + img*img)
                                continue
                            except ValueError:
                                pass
                    try:
                        parsed[i] = float(val)
                    except ValueError:
                        parsed[i] = 0.0
                elif isinstance(val, (int, float)):
                    parsed[i] = float(val)
            out_matrix[:, j] = parsed
        else:
            out_matrix[:, j] = col_data.astype(np.float32)
            
    return out_matrix

def build_sliding_windows(df, subcarrier_cols, seq_len=100, step_size=20):
    """
    Extracts 64-subcarrier features and generates sliding windows with categorical targets based on variance & energy.
    """
    data = parse_csi_array(df, subcarrier_cols)
    num_samples = len(data)
    windows = []
    labels = []
    
    for start in range(0, num_samples - seq_len + 1, step_size):
        end = start + seq_len
        window = data[start:end] # (seq_len, 64)
        
        # Determine movement/activity target class from signal dynamics
        window_var = np.var(window)
        if window_var > 15.0:
            label = 3 # High activity / Position change / Fall
        elif window_var > 5.0:
            label = 2 # Moderate activity / Restlessness
        elif window_var > 1.0:
            label = 1 # Light movement / Micro-motion
        else:
            label = 0 # Stationary / Rest / Deep Sleep
            
        windows.append(window.T) # Transpose to (64, seq_len) for 1D-CNN format
        labels.append(label)
        
    if not windows:
        return np.empty((0, 64, seq_len), dtype=np.float32), np.empty((0,), dtype=np.int64), data
        
    return np.array(windows, dtype=np.float32), np.array(labels, dtype=np.int64), data

def load_csi_dataloaders(config):
    """
    Loads CSI CSV files, performs SUBJECT-BASED SPLIT to prevent data leakage,
    fits scaler on train split only, and returns PyTorch DataLoaders.
    """
    data_dir = config['dataset']['dir']
    seq_len = config['dataset']['sequence_length']
    step_size = config['dataset']['step_size']
    
    csv_files = sorted(glob.glob(os.path.join(data_dir, '*.csv')))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in dataset directory: {data_dir}")
        
    print(f"📁 Loaded {len(csv_files)} subject CSV files from {data_dir}")
    
    # Subject-based train/val/test split to prevent data leakage
    num_files = len(csv_files)
    train_end = int(num_files * config['dataset']['train_ratio'])
    val_end = train_end + int(num_files * config['dataset']['val_ratio'])
    
    train_files = csv_files[:train_end]
    val_files = csv_files[train_end:val_end]
    test_files = csv_files[val_end:]
    
    print(f"🔒 Data Leakage Prevention Split: Train ({len(train_files)} subjects), Val ({len(val_files)} subjects), Test ({len(test_files)} subjects)")
    
    subcarrier_cols = [f"SC_{i}" for i in range(64)]
    
    # Load raw numpy matrices for train set to fit scaler
    print("⏳ Parsing training subject files and fitting scaler...")
    train_matrices = []
    for f in train_files:
        df = pd.read_csv(f)
        matrix = parse_csi_array(df, subcarrier_cols)
        train_matrices.append(matrix)
        
    scaler = StandardScaler()
    combined_train_raw = np.vstack(train_matrices)
    scaler.fit(combined_train_raw)
    
    def process_file_list(file_list):
        all_x, all_y = [], []
        for f in file_list:
            df = pd.read_csv(f)
            matrix = parse_csi_array(df, subcarrier_cols)
            # Scale using training scaler
            matrix_scaled = scaler.transform(matrix)
            
            # Generate sliding windows
            num_samples = len(matrix_scaled)
            windows = []
            labels = []
            for start in range(0, num_samples - seq_len + 1, step_size):
                end = start + seq_len
                window = matrix_scaled[start:end] # (seq_len, 64)
                window_var = np.var(window)
                if window_var > 15.0: label = 3
                elif window_var > 5.0: label = 2
                elif window_var > 1.0: label = 1
                else: label = 0
                windows.append(window.T)
                labels.append(label)
                
            if len(windows) > 0:
                all_x.append(np.array(windows, dtype=np.float32))
                all_y.append(np.array(labels, dtype=np.int64))
                
        return np.vstack(all_x), np.concatenate(all_y)
        
    X_train, y_train = process_file_list(train_files)
    X_val, y_val = process_file_list(val_files)
    X_test, y_test = process_file_list(test_files)
    
    print(f"📊 Dataset Sequences Created: Train={X_train.shape}, Val={X_val.shape}, Test={X_test.shape}")
    
    # Create PyTorch Datasets
    aug_fn = apply_augmentation if config['dataset'].get('augmentation', False) else None
    train_dataset = CSIDataset(X_train, y_train, transform=aug_fn)
    val_dataset = CSIDataset(X_val, y_val)
    test_dataset = CSIDataset(X_test, y_test)
    
    # PyTorch DataLoaders with GPU optimizations
    batch_size = config['training']['batch_size']
    num_workers = config['hardware'].get('num_workers', 4)
    pin_mem = config['hardware'].get('pin_memory', True)
    
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=pin_mem, persistent_workers=(num_workers > 0)
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=pin_mem, persistent_workers=(num_workers > 0)
    )
    test_loader = DataLoader(
        test_dataset, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=pin_mem, persistent_workers=(num_workers > 0)
    )
    
    return train_loader, val_loader, test_loader, scaler
