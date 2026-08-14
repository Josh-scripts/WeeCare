import serial
import time

print("Connecting to COM11 for TX script setup...")
ser = serial.Serial('COM11', 115200, timeout=1)
time.sleep(1)
ser.write(b'\r\n\x03\x03') # Ctrl+C to interrupt
time.sleep(0.5)

script = """import network, time, socket
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(ssid="WeeCare_TX", channel=6)
print("LIVE_TX_WIFI_BEACON_ACTIVE")
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
while True:
    try:
        s.sendto(b'ping', ('255.255.255.255', 5000))
    except Exception:
        pass
    time.sleep(0.01) # Send packets at 100Hz
"""

ser.write(b"f = open('main.py', 'w')\r\n")
time.sleep(0.5)
for line in script.splitlines():
    ser.write(('f.write(' + repr(line + '\\n') + ')\\r\\n').encode())
    time.sleep(0.1)
ser.write(b"f.close()\r\n")
time.sleep(0.5)

ser.write(b"\x04") # Ctrl+D soft reset
time.sleep(1)
print("ESP32 Transmitter Provisioned successfully!")
ser.close()
