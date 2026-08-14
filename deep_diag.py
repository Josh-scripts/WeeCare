"""
Deep diagnostic: print EVERYTHING from COM12, including connection status,
raw bytes, and any errors. Run this standalone to diagnose the ESP32 receiver.
"""
import serial
import time

PORT = "COM12"
BAUD = 115200

print(f"Opening {PORT} at {BAUD} baud...")
try:
    ser = serial.Serial()
    ser.port = PORT
    ser.baudrate = BAUD
    ser.timeout = 0.1
    ser.dtr = False
    ser.rts = False
    ser.open()
    print(f"SUCCESS: {PORT} opened!")
    print(f"  in_waiting before sleep: {ser.in_waiting}")
    time.sleep(2)  # give ESP32 time to boot/send
    print(f"  in_waiting after 2s: {ser.in_waiting}")

    print("\n--- Listening for 10 seconds ---")
    start = time.time()
    total_bytes = 0
    line_count = 0
    while time.time() - start < 10:
        if ser.in_waiting > 0:
            raw = ser.read(ser.in_waiting)
            total_bytes += len(raw)
            decoded = raw.decode('utf-8', errors='replace')
            print(f"[BYTES={len(raw)}] {repr(decoded)}")
        else:
            time.sleep(0.05)
    
    print(f"\n--- SUMMARY: received {total_bytes} bytes total ---")
    if total_bytes == 0:
        print("!!! NO DATA received from ESP32 !!!")
        print("Possible reasons:")
        print("  1. Receiver not connected to Transmitter AP (wrong SSID/password)")
        print("  2. esp_wifi_set_csi() not supported on this Arduino core version")
        print("  3. ESP32 crashed silently after boot (needs a Serial.println in setup)")
    ser.close()

except serial.SerialException as e:
    print(f"FAILED to open {PORT}: {e}")
