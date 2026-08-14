import serial
import time

try:
    ser = serial.Serial('COM12', 115200, timeout=1)
    time.sleep(1)
    # Stop whatever is running
    ser.write(b'\r\n\x03\x03\x03\r\n')
    time.sleep(0.5)
    ser.reset_input_buffer()
    
    # Send a print command
    ser.write(b'print("HELLO_FROM_ESP32")\r\n')
    time.sleep(1)
    
    # Read everything
    output = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    print("ESP32 Response:")
    print(output)
    ser.close()
except Exception as e:
    print(f"Error: {e}")
