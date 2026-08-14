import serial
import time

try:
    print("Opening COM12 with default DTR/RTS (forces hard reset)...")
    ser = serial.Serial('COM12', 115200, timeout=1)
    
    print("Listening to COM12 (Receiver) for 10 seconds...")
    start = time.time()
    while time.time() - start < 10:
        if ser.in_waiting:
            print(ser.read(ser.in_waiting).decode('utf-8', errors='ignore'), end='', flush=True)
        time.sleep(0.1)
    ser.close()
except Exception as e:
    print(e)
