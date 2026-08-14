import serial
import time
import sys

def check_com12():
    try:
        ser = serial.Serial('COM12', 115200, timeout=1)
        print("Connected to COM12! Listening for CSI_DATA...")
        start_time = time.time()
        count = 0
        while time.time() - start_time < 5:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(line)
                    count += 1
                    if count >= 15: 
                        print("Received 15 valid lines. Closing...")
                        break
        ser.close()
        print("Test complete.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == '__main__':
    check_com12()
