# 🧠 Vital Signs AI Monitor — Setup Guide

## Prerequisites

Before starting, make sure your friend's laptop has:
- **Python 3.10 or 3.11** installed → https://python.org/downloads
- **Arduino IDE** (to flash the ESP32s) → https://www.arduino.cc/en/software

---

## Step 1 – Copy the Project Folder

Copy the entire `vital_signs_app` folder to their laptop. You can use a USB drive, Google Drive, or any file sharing method.

---

## Step 2 – Install Python Dependencies

Open a terminal (PowerShell or CMD), navigate into the `vital_signs_app` folder, then run:

```bash
# Create a fresh virtual environment
python -m venv venv

# Activate it (Windows)
.\venv\Scripts\activate

# Install all required packages
pip install -r requirements.txt
```

> ⚠️ **Note:** `torch` (PyTorch) is a large package (~2GB download). Make sure the laptop has a good internet connection.

---

## Step 3 – Flash the ESP32 Devices

Use Arduino IDE to flash the two ESP32 boards:

1. Open Arduino IDE
2. Go to `File → Open` and open the respective `.ino` file
3. Select `Tools → Board → ESP32 Dev Module`
4. Select the correct COM port
5. Click **Upload**

| ESP32 | File to Flash |
|---|---|
| Transmitter | `esp32_csi_transmitter.ino` |
| Receiver (plugged into laptop via USB) | `esp32_csi_receiver.ino` |

> 📌 The Receiver ESP32 must stay **plugged into the laptop via USB** at all times.
> Check which COM port the Receiver is on (`Device Manager → Ports`) and update `COM5` in `main.py` if needed.

---

## Step 4 – Run the AI Backend

In the terminal (with venv activated):

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

---

## Step 5 – Open the Dashboard

Open a web browser and go to:

**http://127.0.0.1:8000**

The dashboard will show:
- ❤️ Live Heart Rate (BPM)
- 🫁 Live Breathing Rate (BPM)
- 📡 ESP32 Connection Status (Green = Connected, Red = Disconnected)
- 🧠 AI Sleep Stage Analysis

---

## How it Works

```
[Transmitter ESP32] ──WiFi CSI──► [Receiver ESP32 via USB] ──Serial──► [Python AI Backend] ──WebSocket──► [Web Dashboard]
```

The system uses the **ruvnet/wifi-densepose-pretrained** PyTorch model from Hugging Face to analyze Wi-Fi signal distortions caused by your body movements and extract vital signs — no wearables needed!

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Dashboard says "Disconnected" | Make sure both ESP32s are powered on and the Receiver is plugged into USB |
| COM port error | Open Device Manager and check which port the Receiver ESP32 is on, update `main.py` line ~180 |
| `torch` import error | Run `pip install torch` inside the venv |
| Port 8000 already in use | Run `uvicorn main:app --host 127.0.0.1 --port 8001` and open `http://127.0.0.1:8001` |
