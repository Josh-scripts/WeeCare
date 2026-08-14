import os
import yaml
import torch
from models.csi_net_1d import CSINet1D
from models.csi_transformer import CSITransformer

def export_trained_model():
    config_path = "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    output_dir = config['training']['output_dir']
    checkpoint_path = os.path.join(output_dir, "best_model.pt")
    
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found at {checkpoint_path}")
        
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    model_name = config['model']['name']
    in_channels = config['model']['in_channels']
    hidden_dim = config['model']['hidden_dim']
    num_classes = config['model']['num_classes']
    
    if model_name == "csi_net_1d":
        model = CSINet1D(in_channels=in_channels, hidden_dim=hidden_dim, num_classes=num_classes)
    else:
        model = CSITransformer(in_channels=in_channels, hidden_dim=hidden_dim, num_classes=num_classes)
        
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    dummy_input = torch.randn(1, 64, config['dataset']['sequence_length'])
    
    # 1. Export to TorchScript
    scripted_model = torch.jit.trace(model, dummy_input)
    torchscript_path = os.path.join(output_dir, "model_torchscript.pt")
    scripted_model.save(torchscript_path)
    print(f"✅ Exported TorchScript model -> {torchscript_path}")
    
    # 2. Export to ONNX
    onnx_path = os.path.join(output_dir, "model.onnx")
    torch.onnx.export(
        model, dummy_input, onnx_path,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=['csi_input'],
        output_names=['activity_prediction'],
        dynamic_axes={'csi_input': {0: 'batch_size'}, 'activity_prediction': {0: 'batch_size'}}
    )
    print(f"✅ Exported ONNX model -> {onnx_path}")

if __name__ == "__main__":
    export_trained_model()
