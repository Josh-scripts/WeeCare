import serial
import time

s = serial.Serial('COM5', 115200, timeout=2)
print("Opened COM5")
time.sleep(1)

s.write(b'\r\n\x03\x03\r\n')
time.sleep(0.5)
s.read_all()

s.write(b'import network\r\n')
time.sleep(0.1)
s.write(b'w = network.WLAN(network.STA_IF)\r\n')
time.sleep(0.1)
s.write(b'w.active(True)\r\n')
time.sleep(0.5)
s.write(b'print(w.scan())\r\n')
time.sleep(3)

output = s.read_all().decode('utf-8', errors='ignore')
print("OUTPUT:")
print(output)
s.close()
