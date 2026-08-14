import serial
import time

print("Connecting to COM5 for MicroPython script setup...")
ser = serial.Serial('COM5', 115200, timeout=1)
time.sleep(1)
ser.write(b'\r\n\x03\x03') # Ctrl+C to interrupt
time.sleep(0.5)

script = """import sys, time
count = 0
while True:
    count += 1
    amp = 45.0 + (count % 15) * 0.5
    phase = (count % 100) / 100.0 * 6.28
    sys.stdout.write(f"{amp:.2f},{phase:.2f}\\n")
    time.sleep(0.05)
"""

ser.write(b"f = open('main.py', 'w')\r\n")
time.sleep(0.5)
for line in script.splitlines():
    ser.write(f"f.write({repr(line + '\n')})\r\n".encode())
    time.sleep(0.1)
ser.write(b"f.close()\r\n")
time.sleep(0.5)

ser.write(b"\x04") # Ctrl+D soft reset
time.sleep(1)
print("ESP32 MicroPython main.py written and soft-reset successfully!")
ser.close()
