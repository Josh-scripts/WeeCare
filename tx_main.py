import network, time, socket
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
