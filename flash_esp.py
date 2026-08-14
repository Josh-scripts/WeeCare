import os
import sys
import urllib.request
import subprocess

FIRMWARE_URL = 'https://micropython.org/resources/firmware/ESP32_GENERIC-20240105-v1.22.1.bin'
FIRMWARE_FILE = 'micropython.bin'

if not os.path.exists(FIRMWARE_FILE):
    print("Downloading MicroPython firmware...")
    urllib.request.urlretrieve(FIRMWARE_URL, FIRMWARE_FILE)
    print("Download complete.")

port = sys.argv[1]
print(f"Erasing flash on {port}...")
subprocess.run([sys.executable, "-m", "esptool", "--chip", "esp32", "--port", port, "erase_flash"], check=True)

print(f"Flashing MicroPython on {port}...")
subprocess.run([sys.executable, "-m", "esptool", "--chip", "esp32", "--port", port, "--baud", "460800", "write_flash", "-z", "0x1000", FIRMWARE_FILE], check=True)
print("Flashed successfully!")
