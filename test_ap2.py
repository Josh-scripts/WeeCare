import serial
import time

s = serial.Serial('COM5', 115200, timeout=1)
s.dtr = False
s.rts = False
s.open()
s.close()
s = serial.Serial('COM5', 115200, timeout=2) # Will reset
time.sleep(1)
s.write(b'\r\n\x03\x03\r\n')
time.sleep(0.5)

script = """
import network
try:
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(ssid="WeeCare_TX", channel=6)
    print("SUCCESS_AP")
except Exception as e:
    print("AP_ERROR:", repr(e))
"""

s.write(b'def test():\r\n')
for line in script.split('\n'):
    s.write(f'    {line}\r\n'.encode())
s.write(b'\r\n')
time.sleep(0.5)
s.read_all()
s.write(b'test()\r\n')
time.sleep(1)
print("OUTPUT:")
print(s.read_all().decode('utf-8', errors='ignore'))
s.close()
