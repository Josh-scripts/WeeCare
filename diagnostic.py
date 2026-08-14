import serial
import time
import threading

def monitor_port(port, duration=5):
    try:
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = 115200
        ser.timeout = 0.5
        # Don't assert DTR/RTS to avoid holding ESP32 in reset
        ser.dtr = False
        ser.rts = False
        ser.open()
        
        print(f"[{port}] Listening...")
        start = time.time()
        while time.time() - start < duration:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"[{port}] {line}")
            time.sleep(0.01)
        ser.close()
    except Exception as e:
        print(f"[{port}] Failed: {e}")

if __name__ == '__main__':
    t1 = threading.Thread(target=monitor_port, args=('COM11',))
    t2 = threading.Thread(target=monitor_port, args=('COM12',))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    print("Diagnostics complete.")
