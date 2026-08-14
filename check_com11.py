import serial
import time

try:
    ser = serial.Serial('COM11', 115200, timeout=1)
    time.sleep(0.5)
    ser.write(b'\r\n\x04')
    time.sleep(0.5)
    
    print("Listening to COM11 (Transmitter)...")
    start = time.time()
    while time.time() - start < 5:
        if ser.in_waiting:
            print(ser.read(ser.in_waiting).decode('utf-8', errors='ignore'), end='')
        time.sleep(0.1)
    ser.close()
except Exception as e:
    print(e)
