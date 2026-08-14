import serial
import time

s = serial.Serial('COM5', 115200, timeout=2)
s.write(b'\r\n\x03\x03\r\n')
time.sleep(1)
s.read_all()

s.write(b'import network\r\n')
s.write(b'try:\r\n')
s.write(b'    ap=network.WLAN(network.AP_IF)\r\n')
s.write(b'    ap.active(True)\r\n')
s.write(b'    ap.config(essid="WeeCare_TX", channel=6)\r\n')
s.write(b'    print("AP_SUCCESS")\r\n')
s.write(b'except Exception as e:\r\n')
s.write(b'    print("ERROR:", e)\r\n')
s.write(b'\r\n')
time.sleep(2)
print("OUTPUT:")
print(s.read_all().decode('utf-8', errors='ignore'))
s.close()
