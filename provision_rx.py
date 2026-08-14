import serial
import time

print("Connecting to COM12 for RX script setup...")
ser = serial.Serial('COM12', 115200, timeout=1)
time.sleep(1)
ser.write(b'\r\n\x03\x03') # Ctrl+C to interrupt
time.sleep(0.5)

script = """import network, time
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("WeeCare_TX")

print("LIVE_RX_SEARCHING")
scan_count = 0
while not wlan.isconnected():
    time.sleep(0.1)
    scan_count += 1
    if scan_count % 30 == 0:
        # Every 3 seconds, if still not connected, do a scan
        try:
            networks = wlan.scan()
            ssids = [n[0].decode('utf-8') for n in networks]
            print(f"WIFI_SCAN:{','.join(ssids)}")
        except Exception:
            pass
    if scan_count % 10 == 0:
        # Print 0.0 so the chart draws a flatline while searching
        print("0.0,0.0")

print("LIVE_RX_CONNECTED")
while True:
    try:
        rssi = wlan.status('rssi')
        print(f"{abs(rssi):.2f},0.00")
    except Exception:
        print("0.0,0.0")
    time.sleep(0.01) # 100 Hz sampling rate
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
print("ESP32 Receiver Provisioned successfully!")
ser.close()
