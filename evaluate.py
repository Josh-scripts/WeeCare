import os
import yaml
import torch
import torch.nn as nn
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
from dataset_loader import load_csi_dataloaders
from models.csi_net_1d import CSINet1D
from models.csi_transformer import CSITransformer

def evaluate_test_set():
    config_path = "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    checkpoint_path = os.path.join(config['training']['output_dir'], "best_model.pt")
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"No checkpoint found at {checkpoint_path}. Train the model first!")
        
    print(f"Loading checkpoint from: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Evaluating on device: {device}")
    
    _, _, test_loader, _ = load_csi_dataloaders(config)
    
    model_name = config['model']['name']
    in_channels = config['model']['in_channels']
    hidden_dim = config['model']['hidden_dim']
    num_classes = config['model']['num_classes']
    
    if model_name == "csi_net_1d":
        model = CSINet1D(in_channels=in_channels, hidden_dim=hidden_dim, num_classes=num_classes)
    else:
        model = CSITransformer(in_channels=in_channels, hidden_dim=hidden_dim, num_classes=num_classes)
        
    model.load_state_dict(checkpoint['model_state_dict'])
    model = model.to(device)
    model.eval()
    
    all_preds = []
    all_targets = []
    
    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            batch_x = batch_x.to(device)
            outputs = model(batch_x)
            _, preds = torch.max(outputs, 1)
            
            all_preds.extend(preds.cpu().numpy())
            all_targets.extend(batch_y.numpy())
            
    all_preds = np.array(all_preds)
    all_targets = np.array(all_targets)
    
    class_names = ["Rest / Deep Sleep", "Light Motion", "Restlessness", "High Activity / Fall"]
    
    print("\n" + "="*60)
    print(" 📊 HELD-OUT TEST SET EVALUATION REPORT (Zero Data Leakage)")
    print("="*60)
    
    present_classes = np.unique(np.concatenate([all_targets, all_preds]))
    target_names = [class_names[c] for c in present_classes]
    
    report = classification_report(all_targets, all_preds, labels=present_classes, target_names=target_names, digits=4)
    print(report)
    
    cm = confusion_matrix(all_targets, all_preds, labels=present_classes)
    
    # Save Confusion Matrix Plot
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=target_names, yticklabels=target_names)
    plt.title('Wi-Fi CSI Model — Confusion Matrix (Test Set)')
    plt.ylabel('Ground Truth Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    
    plot_path = os.path.join(config['training']['output_dir'], "confusion_matrix.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f" Saved Confusion Matrix Plot -> {plot_path}")

if __name__ == "__main__":
    evaluate_test_set()
