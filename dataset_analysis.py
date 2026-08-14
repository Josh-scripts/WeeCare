import pandas as pd
import numpy as np
import os
import glob

def analyze_vital_signs():
    print("=== Analyzing Vital Signs Dataset ===")
    vital_dir = r"d:\WeeCare\Dataset\Sleep Disturbances Dataset\Vital Signs"
    
    csi_file = os.path.join(vital_dir, "Breathing - 12 BPM - CSI.csv")
    label_file = os.path.join(vital_dir, "Breathing - Belt & HR.csv")
    
    print(f"Loading CSI data: {os.path.basename(csi_file)}")
    df_csi = pd.read_csv(csi_file)
    print(f"CSI Shape: {df_csi.shape}")
    print(f"CSI Columns: {df_csi.columns.tolist()[:5]} ... {df_csi.columns.tolist()[-5:]}")
    print(f"CSI Time range: {df_csi.iloc[0]['timestamp']} to {df_csi.iloc[-1]['timestamp']}")
    
    # Parse a sample CSI_DATA row
    sample_csi_str = df_csi.iloc[0]['CSI_DATA']
    if pd.notna(sample_csi_str):
        if sample_csi_str.startswith('[') and sample_csi_str.endswith(']'):
            sample_csi_arr = np.fromstring(sample_csi_str[1:-1], sep=' ')
            if len(sample_csi_arr) == 0:
                sample_csi_arr = np.fromstring(sample_csi_str[1:-1], sep=',')
            print(f"Sample CSI_DATA Length: {len(sample_csi_arr)}")
            print(f"Sample CSI_DATA: {sample_csi_arr[:5]} ... {sample_csi_arr[-5:]}")
    
    print(f"\nLoading Label data: {os.path.basename(label_file)}")
    # Handle the weird `'0:0:0.0` format in the label file
    df_labels = pd.read_csv(label_file)
    print(f"Labels Shape: {df_labels.shape}")
    print(f"Labels Columns: {df_labels.columns.tolist()}")
    print(f"Labels Time range: {df_labels.iloc[0]['Time']} to {df_labels.iloc[-1]['Time']}")
    
    print("\nLabel Stats:")
    print(df_labels.describe())
    
    print("\nMissing values in Labels:")
    print(df_labels.isnull().sum())

if __name__ == "__main__":
    analyze_vital_signs()
