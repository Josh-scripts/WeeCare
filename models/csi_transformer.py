import math
import torch
import torch.nn as nn
import torch.nn.functional as F

class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=500):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x):
        # x shape: (Batch, Seq_len, d_model)
        return x + self.pe[:, :x.size(1)]

class CSITransformer(nn.Module):
    """
    Modern 1D CNN + Multi-Head Transformer Encoder for CSI temporal sequence modeling.
    """
    def __init__(self, in_channels=64, hidden_dim=128, num_classes=4, nhead=4, num_layers=2, dropout=0.2):
        super().__init__()
        # Conv feature projection
        self.conv_in = nn.Sequential(
            nn.Conv1d(in_channels, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU()
        )
        self.pos_encoder = PositionalEncoding(hidden_dim)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim, nhead=nhead, dim_feedforward=hidden_dim * 4,
            dropout=dropout, activation='gelu', batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        self.fc_head = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, num_classes)
        )

    def forward(self, x):
        # x shape: (Batch, in_channels=64, seq_len=100)
        h = self.conv_in(x).transpose(1, 2) # Shape: (Batch, seq_len, hidden_dim)
        h = self.pos_encoder(h)
        out = self.transformer(h) # (Batch, seq_len, hidden_dim)
        out_pooled = out.mean(dim=1) # Global Average Pooling over time
        return self.fc_head(out_pooled)
