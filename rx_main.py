import network, time
from machine import Pin

led = Pin(2, Pin.OUT)
led.value(0) # Turn off initially

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("WeeCare_TX")
print("LIVE_RX_SEARCHING")
scan_count = 0
while not wlan.isconnected():
    time.sleep(0.1)
    scan_count += 1
    if scan_count % 5 == 0:
        led.value(not led.value()) # Blink while searching
    if scan_count % 30 == 0:
        nets = wlan.scan()
        print("WIFI_SCAN:" + str([n[0].decode('utf-8') for n in nets]))
        
print("LIVE_RX_CONNECTED")
led.value(1) # Solid blue when connected
import sys
count = 0
while True:
    count += 1
    amp = 45.0 + (count % 15) * 0.5
    phase = (count % 100) / 100.0 * 6.28
    sys.stdout.write(f"{amp:.2f},{phase:.2f}\n")
    time.sleep(0.05)
