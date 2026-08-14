import serial
import time
import sys

def check_com12():
    try:
        ser = serial.Serial()
        ser.port = 'COM12'
        ser.baudrate = 115200
        ser.timeout = 1
        ser.dtr = False
        ser.rts = False
        ser.open()
        
        print("Connected to COM12! Listening for ANY data...")
        start_time = time.time()
        while time.time() - start_time < 5:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(line)
        ser.close()
        print("Test complete.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == '__main__':
    check_com12()
