import torch
import torch.nn as nn
import torch.nn.functional as F

class Conv1DBlock(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1, padding=1):
        super().__init__()
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, stride, padding)
        self.bn = nn.BatchNorm1d(out_channels)
        self.act = nn.GELU()

    def forward(self, x):
        return self.act(self.bn(self.conv(x)))

class CSINet1D(nn.Module):
    """
    Lightweight 1D-CNN architecture optimized for ultra-fast CSI signal classification & vital signs estimation.
    """
    def __init__(self, in_channels=64, hidden_dim=128, num_classes=4, dropout=0.2):
        super().__init__()
        self.layer1 = Conv1DBlock(in_channels, 64, kernel_size=5, padding=2)
        self.pool1 = nn.MaxPool1d(2)
        
        self.layer2 = Conv1DBlock(64, hidden_dim, kernel_size=3, padding=1)
        self.pool2 = nn.MaxPool1d(2)
        
        self.layer3 = Conv1DBlock(hidden_dim, hidden_dim * 2, kernel_size=3, padding=1)
        self.pool3 = nn.AdaptiveAvgPool1d(1)
        
        self.drop = nn.Dropout(dropout)
        self.fc1 = nn.Linear(hidden_dim * 2, 64)
        self.fc_out = nn.Linear(64, num_classes)

    def forward(self, x):
        # Input shape: (Batch, 64_subcarriers, Seq_len=100)
        h = self.pool1(self.layer1(x))
        h = self.pool2(self.layer2(h))
        h = self.pool3(self.layer3(h)).squeeze(-1) # (Batch, hidden_dim * 2)
        h = self.drop(F.gelu(self.fc1(h)))
        return self.fc_out(h)
