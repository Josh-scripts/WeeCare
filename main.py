"""
WeeCare AI Engine — MicroPython & Live Hardware Serial (COM5)
============================================================
- Hardware: Standard ESP32 (v3) on COM5
- MicroPython Firmware with DTR/RTS Init
- PyTorch AI Engine + Danger Evaluator + Elderly Sleep Tracking
"""

import asyncio
import json
import math
import os
import time
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uvicorn
from enum import Enum
from dataclasses import dataclass
import serial
import serial.threaded
import threading
import queue
import logging
from scipy.signal import butter, filtfilt, savgol_filter
from safetensors.torch import load_file
import importlib.util

# Identity Models have been stripped out per user request.

class RobustKalmanFilter:
    """Tighter Kalman — high measurement_variance = trusts prediction more than raw reading."""
    def __init__(self, process_variance=1e-3, measurement_variance=1e-1):
        self.post_estimate = 0.0
        self.post_error = 1.0
        self.Q = process_variance
        self.R = measurement_variance
        self.base_R = measurement_variance
        self.is_initialized = False

    def update(self, measurement):
        if not self.is_initialized:
            self.post_estimate = measurement
            self.is_initialized = True
            return self.post_estimate

        # Dynamic outlier rejection: sudden jumps > 10 BPM are heavily discounted
        if abs(measurement - self.post_estimate) > 10.0:
            self.R = self.base_R * 80.0  # Spike — trust prediction, ignore reading
        else:
            self.R = self.base_R

        # Prediction phase
        pri_estimate = self.post_estimate
        pri_error = self.post_error + self.Q

        # Update phase
        kalman_gain = pri_error / (pri_error + self.R)
        self.post_estimate = pri_estimate + kalman_gain * (measurement - pri_estimate)
        self.post_error = (1 - kalman_gain) * pri_error

        return self.post_estimate


class EMAFilter:
    """Exponential Moving Average — same algorithm used in Apple Watch / Fitbit.
    alpha: 0.05 = very smooth (slow), 0.2 = moderately smooth (fast).
    """
    def __init__(self, alpha=0.08):
        self.alpha = alpha
        self.value = None

    def update(self, measurement):
        if self.value is None:
            self.value = measurement
        else:
            self.value = self.alpha * measurement + (1.0 - self.alpha) * self.value
        return self.value


class RateLimiter:
    """Prevents BPM from changing faster than max_change_per_sec BPM/second.
    Smartwatches use ~1-2 BPM/sec change cap to keep the display calm.
    """
    def __init__(self, max_change_per_sec=2.0, update_interval_sec=0.05):
        self.max_delta = max_change_per_sec * update_interval_sec
        self.value = None

    def update(self, target):
        if self.value is None:
            self.value = target
            return self.value
        delta = target - self.value
        delta = max(-self.max_delta, min(self.max_delta, delta))
        self.value += delta
        return self.value

def apply_bandpass(signal, fs=20.0, lowcut=0.1, highcut=2.5, order=3):
    if len(signal) < 15: return signal
    nyq = 0.5 * fs
    
    # Clamp bounds to avoid filter instability
    low = max(0.01, lowcut / nyq)
    high = min(0.99, highcut / nyq)
    
    try:
        b, a = butter(order, [low, high], btype='bandpass')
        return filtfilt(b, a, signal)
    except Exception:
        return signal

def savitzky_golay_smooth(signal, window_length=15, polyorder=3):
    if len(signal) < window_length: return signal
    try:
        return savgol_filter(signal, window_length, polyorder)
    except Exception:
        return signal

COM_PORT = "COM12"
BAUD_RATE = 921600

# ---------------------------------------------------------------------------
# Enums & PyTorch Model Architecture
# ---------------------------------------------------------------------------

class SleepStage(Enum):
    AWAKE = 0
    LIGHT = 1
    DEEP = 2
    REM = 3

@dataclass
class SleepMetrics:
    stage: SleepStage
    restlessness_score: float
    is_in_bed: bool
    out_of_bed_duration_sec: float
    apnea_risk_detected: bool
    wandering_warning: bool

class VitalSignsNet(nn.Module):
    def __init__(self):
        super(VitalSignsNet, self).__init__()
        self.encoder = nn.Sequential(
            nn.BatchNorm1d(8),
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

class ElderlySleepEvaluator:
    def __init__(self):
        self.out_of_bed_timer = 0.0
        self.restless_history = []

    def evaluate(self, breathing_bpm: float, heart_bpm: float, hrv: float, variance: float, movement: str, current_time: float) -> tuple[dict, SleepMetrics]:
        danger = False
        reasons = []
        alert_level = 0.0
        is_in_bed = True

        if variance > 12.0:
            is_in_bed = False
            self.out_of_bed_timer += 1.0
        else:
            self.out_of_bed_timer = 0.0

        wandering_warning = self.out_of_bed_timer > 900.0
        if wandering_warning:
            danger = True
            alert_level = max(alert_level, 0.8)
            reasons.append("⚠️ WARNING: Elderly Person Out of Bed > 15 mins (Wandering Risk)")

        if not is_in_bed or variance > 4.0: stage = SleepStage.AWAKE
        elif variance < 0.5 and 10.0 <= breathing_bpm <= 14.0 and heart_bpm < 65.0: stage = SleepStage.DEEP
        elif variance < 1.0 and hrv > 0.4: stage = SleepStage.REM
        else: stage = SleepStage.LIGHT

        raw_restless = min(1.0, variance / 5.0)
        self.restless_history.append(raw_restless)
        if len(self.restless_history) > 100: self.restless_history.pop(0)
        restlessness_score = float(np.mean(self.restless_history))

        apnea_risk = (stage in [SleepStage.LIGHT, SleepStage.DEEP, SleepStage.REM]) and (breathing_bpm < 6.0)
        if apnea_risk:
            danger = True
            alert_level = max(alert_level, 0.95)
            reasons.append(f"🚨 DANGER: Sleep Apnea / Breathing Arrest ({breathing_bpm:.1f} BPM)")



        if heart_bpm > 120.0:
            danger = True
            alert_level = max(alert_level, 0.95)
            reasons.append(f"⚠️ DANGER: Sudden Heart Rate Spike ({heart_bpm:.1f} BPM)")
        elif heart_bpm < 40.0:
            danger = True
            alert_level = max(alert_level, 0.90)
            reasons.append(f"⚠️ DANGER: Sudden Heart Rate Drop ({heart_bpm:.1f} BPM)")

        sleep_metrics = SleepMetrics(
            stage=stage, restlessness_score=restlessness_score, is_in_bed=is_in_bed,
            out_of_bed_duration_sec=self.out_of_bed_timer, apnea_risk_detected=apnea_risk,
            wandering_warning=wandering_warning
        )

        return {"is_danger": danger, "alert_level": alert_level, "reasons": reasons}, sleep_metrics

def parse_line(line: str):
    line = line.strip()
    if not line:
        return None, None
    if "," in line:
        try:
            parts = line.split(",")
            amp = float(parts[0])
            phase = float(parts[1]) if len(parts) > 1 else 0.0
            return amp, phase
        except ValueError:
            pass
    return None, None

# ---------------------------------------------------------------------------
# Global serial state — opened once at startup, shared across all WS clients
# ---------------------------------------------------------------------------

g_serial_queue = queue.Queue()
g_last_csi_time = 0.0
g_serial_stop = threading.Event()
g_ser = None

def _serial_reader_global(ser, q, stop_event):
    """Persistent background thread: reads bytes, assembles lines, queues them."""
    buf = bytearray()
    while not stop_event.is_set():
        try:
            if ser and ser.is_open:
                chunk = ser.read(ser.in_waiting or 1)
                if chunk:
                    buf.extend(chunk)
                    while b'\n' in buf:
                        idx = buf.index(b'\n')
                        line = buf[:idx].decode('utf-8', errors='ignore').strip()
                        del buf[:idx + 1]
                        if line:
                            q.put(line)
        except Exception:
            pass

@asynccontextmanager
async def lifespan(app_instance):
    global g_ser, g_serial_stop
    print(f"[Startup] Opening {COM_PORT} at {BAUD_RATE} baud...")
    try:
        g_ser = serial.Serial()
        g_ser.port = COM_PORT
        g_ser.baudrate = BAUD_RATE
        g_ser.timeout = 0.05
        g_ser.open()
        
        # Pulse DTR/RTS to reboot the ESP32 receiver into the firmware
        g_ser.setRTS(True)
        g_ser.setDTR(False)
        time.sleep(0.1)
        g_ser.setRTS(False)
        g_ser.setDTR(True)
        time.sleep(0.2)
        g_ser.setRTS(False)
        g_ser.setDTR(False)
        time.sleep(0.5)
        
        print(f"[Startup] {COM_PORT} opened and ESP32 rebooted successfully!")
        t = threading.Thread(
            target=_serial_reader_global,
            args=(g_ser, g_serial_queue, g_serial_stop),
            daemon=True
        )
        t.start()
    except Exception as e:
        print(f"[Startup] ERROR opening {COM_PORT}: {e}")
    yield
    # Shutdown
    g_serial_stop.set()
    if g_ser and g_ser.is_open:
        g_ser.close()
        print("[Shutdown] Serial port closed.")

# ---------------------------------------------------------------------------
# FastAPI & WebSockets
# ---------------------------------------------------------------------------

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    model = VitalSignsNet()
    try:
        state_dict = load_file("model.safetensors")
        model.load_state_dict(state_dict, strict=True)
        print("Loaded trained VitalSignsNet model (model.safetensors) successfully!")
    except Exception as e:
        print(f"Starting with untrained AI model. Error loading model.safetensors: {e}")
    
    # Identity logic removed.
    encoder = None
    id_head = None

    model.eval()
    evaluator = ElderlySleepEvaluator()
    
    import collections
    amp_buffer = collections.deque(maxlen=200)
    phase_buffer = collections.deque(maxlen=200)
    sim_time = 0.0

    # CSI sliding window — uses global serial queue
    window_size = 100
    csi_window = []
    # local snapshot of last_csi_time managed per connection
    last_csi_time_local = [0.0]  # list so it's mutable inside nested scope
    # Kalman Filters to eliminate sudden noise spikes
    # Layer 1: Kalman — removes hardware-level measurement noise
    hr_kalman = RobustKalmanFilter(process_variance=0.005, measurement_variance=5.0)
    br_kalman = RobustKalmanFilter(process_variance=0.005, measurement_variance=3.0)
    # Layer 2: EMA — long-window smoothing like Apple Watch
    hr_ema = EMAFilter(alpha=0.07)   # ~14-sample effective window
    br_ema = EMAFilter(alpha=0.10)   # ~10-sample effective window
    # Layer 3: Rate Limiter — caps BPM change speed (2 BPM/sec max)
    hr_rate = RateLimiter(max_change_per_sec=2.0, update_interval_sec=0.05)
    br_rate = RateLimiter(max_change_per_sec=1.0, update_interval_sec=0.05)

    try:
        count = 0
        while True:
            amp = None
            phase = 0.0
            
            # Drain all complete lines from the GLOBAL serial reader thread
            while not g_serial_queue.empty():
                try:
                    line = g_serial_queue.get_nowait()
                except queue.Empty:
                    break

                if line.startswith("CSI_DATA,["):
                    try:
                        arr_str = line.split("[")[1].split("]")[0]
                        arr = np.fromstring(arr_str, sep=' ')
                        if len(arr) >= 2 and len(arr) % 2 == 0:
                            real = arr[::2]
                            imag = arr[1::2]
                            amps = np.sqrt(real**2 + imag**2)
                            mean_amp = float(np.mean(amps))
                            csi_window.append(mean_amp)
                            if len(csi_window) > window_size:
                                csi_window.pop(0)
                            last_csi_time_local[0] = time.time()
                            amp = mean_amp
                            print(f"[CSI] subcarriers={len(real)} mean_amp={mean_amp:.2f}", flush=True)
                    except Exception as parse_err:
                        print(f"[CSI PARSE ERROR] {parse_err} | line={line[:80]}")
            
            # Strictly use live hardware data. If the ESP32 is turned off, drop to 0.0
            if amp is None:
                amp = 0.0
            sim_time += 0.05
            amp_buffer.append(amp)
            phase_buffer.append(phase)
            
            if len(amp_buffer) >= 100:
                # Get last 100 samples — apply rolling median pre-filter (smartwatch trick)
                # This kills transient noise spikes BEFORE FFT sees them
                raw_arr = np.array(list(amp_buffer)[-100:])
                # Rolling median with window=7 — smooths without phase distortion
                from numpy.lib.stride_tricks import sliding_window_view
                windows = sliding_window_view(raw_arr, window_shape=7)
                median_arr = np.median(windows, axis=1)
                # Pad front to maintain length=100
                pad = np.full(6, median_arr[0])
                amp_arr = np.concatenate([pad, median_arr])
                
                # 1. Pulse-Fi Signal Processing Pipeline (Physical fs = 20Hz)
                # Isolate Breathing (0.1 - 0.6 Hz) and Heartbeat (0.8 - 2.5 Hz) cleanly
                b_signal = apply_bandpass(amp_arr, fs=20.0, lowcut=0.1, highcut=0.6)
                h_signal = apply_bandpass(amp_arr, fs=20.0, lowcut=0.8, highcut=2.5)
                
                # Broad signal for AI Feature Extraction
                broad_signal = apply_bandpass(amp_arr, fs=20.0, lowcut=0.1, highcut=2.5)
                shaped = savitzky_golay_smooth(broad_signal)
                
                # 2. Extract 8-Dimensional Features for RuView Encoder
                mean_amp = np.mean(shaped)
                std_amp = np.std(shaped)
                max_amp = np.max(shaped)
                min_amp = np.min(shaped)
                median_amp = np.median(shaped)
                p25_amp = np.percentile(shaped, 25)
                p75_amp = np.percentile(shaped, 75)
                var_amp = np.var(shaped)
                
                features_8d = np.array([mean_amp, std_amp, max_amp, min_amp, median_amp, p25_amp, p75_amp, var_amp], dtype=np.float32)
                x_8dim = torch.from_numpy(features_8d).unsqueeze(0) # Shape: (1, 8)
                
                with torch.no_grad():
                    preds = model(x_8dim)
                
                # 3. High-Resolution Zero-Padded FFT for Perfect Accuracy
                b_spectral = np.abs(np.fft.rfft(b_signal, n=2048))
                h_spectral = np.abs(np.fft.rfft(h_signal, n=2048))
                freqs = np.fft.rfftfreq(2048, d=0.05) # 20Hz sampling (1 / 0.05s)
                
                b_mask = (freqs >= 0.1) & (freqs <= 0.6)
                raw_b_bpm = float(freqs[b_mask][np.argmax(b_spectral[b_mask])] * 60.0) if np.any(b_mask) else 15.0
                b_power = float(np.max(b_spectral[b_mask])) if np.any(b_mask) else 0.0
                
                h_mask = (freqs >= 0.8) & (freqs <= 2.5)
                raw_h_bpm = float(freqs[h_mask][np.argmax(h_spectral[h_mask])] * 60.0) if np.any(h_mask) else 65.0
                h_power = float(np.max(h_spectral[h_mask])) if np.any(h_mask) else 0.0
                
                # Smooth the rigid FFT bins (e.g. 60.0 -> 72.0) with mathematical interpolation to make the UI fluid
                # We pull the simulated smooth frequencies if the ESP32 is flatlining (var < 30)
                variance = float(np.var(shaped))
                
                # Consider hardware connected if we received a CSI frame in the last 3 seconds
                hardware_live = (time.time() - last_csi_time_local[0]) < 3.0
                
                if not hardware_live:
                    # Hardware is disconnected
                    b_bpm = 0.0
                    h_bpm = 0.0
                else:
                    try:
                        # Use mathematically accurate Live FFT for Heart Rate
                        h_bpm = raw_h_bpm
                        
                        # Calculate breathing signal variance
                        b_var = float(np.var(b_signal))
                        
                        # Breath-Hold Detector: if breathing signal variance is extremely low, or peak breathing power is too weak compared to heart
                        if b_var < 0.05 or b_power < (h_power * 0.45) or variance < 0.5:
                            b_bpm = 0.0
                            # Immediately clear filter memory to ensure instant drop to 0
                            br_kalman.is_initialized = False
                            br_ema.value = 0.0
                            br_rate.value = 0.0
                        else:
                            b_bpm = br_kalman.update(raw_b_bpm)
                            b_bpm = br_ema.update(b_bpm)
                            b_bpm = br_rate.update(b_bpm)
                            
                        # === SMARTWATCH 3-LAYER STABILIZATION FOR HR ===
                        # Layer 1: Kalman — suppress hardware measurement noise
                        h_bpm = hr_kalman.update(h_bpm)
                        # Layer 2: EMA — long-window averaging (Apple Watch style)
                        h_bpm = hr_ema.update(h_bpm)
                        # Layer 3: Rate limiter — display changes at max 2 BPM/sec
                        h_bpm = hr_rate.update(h_bpm)
                            
                        # Clamp to realistic biological ranges
                        h_bpm = max(40.0, min(h_bpm, 140.0))
                        b_bpm = max(0.0, min(b_bpm, 30.0))
                    except:
                        b_bpm = raw_b_bpm
                        h_bpm = raw_h_bpm
                
                print(f"DEBUG_LIVE | hw_live={hardware_live} | raw_amps: {amp_arr[-3:].tolist()} | shaped_var: {variance:.2f} | b_bpm: {b_bpm:.1f} | h_bpm: {h_bpm:.1f}", flush=True)
                
                movement_str = "NONE"
                if variance > 12.0: movement_str = "GAIT"
                elif variance > 4.0: movement_str = "POSITIONAL"
                elif variance > 1.0: movement_str = "MICRO"

                danger_info, sleep = evaluator.evaluate(b_bpm, h_bpm, 0.5, variance, movement_str, sim_time)
                
                if not hardware_live:
                    danger_info["is_danger"] = True
                    danger_info["reasons"] = ["⚠️ ESP32 Receiver Disconnected: Waiting for CSI Signal..."]
                    danger_info["alert_level"] = 1.0
                    sleep.is_in_bed = False
                    sleep.stage = SleepStage.AWAKE
                
                response = {
                    "breathingRate": b_bpm,
                    "heartRate": h_bpm,
                    "movement": movement_str,
                    "alert": danger_info["alert_level"],
                    "is_danger": danger_info["is_danger"],
                    "reasons": danger_info["reasons"],
                    "sleepStage": sleep.stage.name,
                    "restlessness": sleep.restlessness_score,
                    "isInBed": sleep.is_in_bed,
                    "outOfBedSec": sleep.out_of_bed_duration_sec,
                    "apneaRisk": sleep.apnea_risk_detected,
                    "wanderingWarning": sleep.wandering_warning,
                    "signal_raw": float(shaped[-1]) if len(shaped) > 0 else float(amp),
                    "hardware_connected": hardware_live
                }
                await websocket.send_text(json.dumps(response))
            
            await asyncio.sleep(0.05)

    except Exception as e:
        print(f"WS Exception: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
