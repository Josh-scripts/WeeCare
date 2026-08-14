import serial
import time
import sys

port = sys.argv[1]
script_file = sys.argv[2]

with open(script_file, 'r') as f:
    script = f.read()

print(f"Connecting to {port}...")
ser = serial.Serial(port, 115200, timeout=1)
time.sleep(1)

# Interrupt and enter raw REPL or just normal REPL
ser.write(b'\r\n\x03\x03') 
time.sleep(1)

# Wait for REPL prompt
print("Waiting for REPL prompt...")
ser.reset_input_buffer()
ser.write(b'\r\n')
timeout = time.time() + 5
while time.time() < timeout:
    if ser.in_waiting:
        out = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        if '>>>' in out:
            print("REPL detected!")
            break
    time.sleep(0.1)

# Write file
ser.write(b"f = open('main.py', 'w')\r\n")
time.sleep(0.5)
for line in script.splitlines():
    ser.write(('f.write(' + repr(line + '\n') + ')\r\n').encode())
    time.sleep(0.1)
ser.write(b"f.close()\r\n")
time.sleep(0.5)

ser.write(b"\x04") # Ctrl+D soft reset
time.sleep(1)
print(f"Provisioned {port} successfully!")
ser.close()
