import serial
import time
import threading

def check_port(port):
    print(f"Opening {port}...")
    try:
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = 115200
        ser.timeout = 0.5
        ser.dtr = False
        ser.rts = False
        ser.open()
        print(f"SUCCESS: {port} opened. Reading...")
        time.sleep(2)
        start = time.time()
        buf = b""
        while time.time() - start < 3:
            if ser.in_waiting > 0:
                buf += ser.read(ser.in_waiting)
            time.sleep(0.1)
        ser.close()
        print(f"RESULT {port}: received {len(buf)} bytes. Content: {repr(buf[:300])}")
    except Exception as e:
        print(f"ERROR {port}: {e}")

threads = []
for port in ["COM7", "COM12"]:
    t = threading.Thread(target=check_port, args=(port,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
