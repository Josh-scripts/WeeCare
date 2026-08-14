import serial
import time

PORT = "COM12"
BAUD = 115200

print(f"Opening {PORT}...")
try:
    ser = serial.Serial()
    ser.port = PORT
    ser.baudrate = BAUD
    ser.timeout = 0.5
    ser.open()
    
    print("Resetting ESP32 via DTR/RTS...")
    # Standard ESP32 reset sequence:
    # 1. RTS = True, DTR = False (EN = High, BOOT = Low)
    # 2. RTS = False, DTR = True (EN = Low, BOOT = High)
    # 3. RTS = False, DTR = False (EN = High, BOOT = High)
    ser.setRTS(True)
    ser.setDTR(False)
    time.sleep(0.1)
    ser.setRTS(False)
    ser.setDTR(True)
    time.sleep(0.2)
    ser.setRTS(False)
    ser.setDTR(False)
    time.sleep(0.5)
    
    print("Listening for 5 seconds...")
    start = time.time()
    buf = b""
    while time.time() - start < 5:
        if ser.in_waiting > 0:
            buf += ser.read(ser.in_waiting)
        time.sleep(0.05)
        
    ser.close()
    print(f"Received {len(buf)} bytes.")
    print("Raw output:", repr(buf))
except Exception as e:
    print(f"ERROR: {e}")
