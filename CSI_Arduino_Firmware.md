# ESP32 CSI Arduino Firmware (High Speed & 20Hz Sampling)

To get fast, low-latency CSI data and prevent the ESP32 serial buffer from overflowing, we need to **increase the baud rate to `921600`** and **tune the packet rate**.

The Python backend's signal processing and PyTorch model expect data at **20Hz** (one packet every 50ms). This is even faster than 200ms and guarantees real-time responsiveness. 

I have updated the sketches below with:
1. **`921600` Baud Rate** for high-speed serial printing.
2. **`50ms` delay** in the Transmitter to send exactly 20 packets per second.

## Transmitter Code (Flash to COM11)
```cpp
#include <WiFi.h>
#include <WiFiUdp.h>

const char *ssid = "WeeCare_TX";
const char *password = "12345678";
WiFiUDP udp;
const char* target_ip = "192.168.4.2"; // Unicast target

void setup() {
  Serial.begin(921600); // High-speed Serial
  WiFi.softAP(ssid, password);
  udp.begin(8888);
  Serial.println("Transmitter AP started. Broadcasting pings...");
}

void loop() {
  udp.beginPacket(target_ip, 8888);
  udp.printf("ping");
  udp.endPacket();
  delay(50); // Send packet every 50ms (20Hz)
}
```

## Receiver Code (Flash to COM12)
```cpp
#include <WiFi.h>
#include <esp_wifi.h>

const char *ssid = "WeeCare_TX";
const char *password = "12345678";

// Static IP Configuration
IPAddress local_IP(192, 168, 4, 2);
IPAddress gateway(192, 168, 4, 1);
IPAddress subnet(255, 255, 255, 0);

// The ESP-IDF callback function that triggers every time a Wi-Fi packet is received
void _csi_rx_cb(void *ctx, wifi_csi_info_t *info) {
  if (!info || !info->buf || info->len == 0) return;
  
  // Output in the exact format our Python backend expects
  Serial.print("CSI_DATA,[");
  
  int8_t *csi_data = (int8_t *)info->buf;
  for (int i = 0; i < info->len; i++) {
    Serial.print(csi_data[i]);
    if (i < info->len - 1) {
      Serial.print(" ");
    }
  }
  Serial.println("]");
}

void setup() {
  Serial.begin(921600); // High-speed Serial
  delay(1000);
  Serial.println("\n--- Booting Receiver ---");
  
  // Configure Static IP
  if (!WiFi.config(local_IP, gateway, subnet)) {
    Serial.println("STA Failed to configure Static IP");
  }
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to Transmitter AP!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  
  // Configure CSI
  wifi_csi_config_t csi_config = {
      .lltf_en           = true,
      .htltf_en          = true,
      .stbc_htltf2_en    = true,
      .ltf_merge_en      = true,
      .channel_filter_en = false,
      .manu_scale        = false,
      .shift             = false,
  };
  
  esp_err_t err;
  
  err = esp_wifi_set_csi(true);
  Serial.printf("esp_wifi_set_csi: %s\n", esp_err_to_name(err));
  
  err = esp_wifi_set_csi_config(&csi_config);
  Serial.printf("esp_wifi_set_csi_config: %s\n", esp_err_to_name(err));
  
  err = esp_wifi_set_csi_rx_cb(_csi_rx_cb, NULL);
  Serial.printf("esp_wifi_set_csi_rx_cb: %s\n", esp_err_to_name(err));
}

void loop() {
  delay(1000);
}
```

## Steps
1. Flash the updated Transmitter code to **COM11** (make sure to select **921600** baud rate if you open the serial monitor).
2. Flash the updated Receiver code to **COM12**.
3. **Close the Arduino Serial Monitor / Arduino IDE completely** so the Python backend can claim the port.
4. Let me know when they are flashed!
