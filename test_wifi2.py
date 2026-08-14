import serial
import time

s = serial.Serial('COM5', 115200, timeout=2)
s.write(b'\r\n\x03\x03\r\n')
time.sleep(0.5)
s.read_all()

s.write(b'import network; w=network.WLAN(network.STA_IF); w.active(True); print([net[0] for net in w.scan()])\r\n')
time.sleep(3)
print(s.read_all().decode('utf-8', errors='ignore'))
s.close()
