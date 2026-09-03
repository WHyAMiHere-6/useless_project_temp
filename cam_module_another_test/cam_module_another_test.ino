#include "esp_camera.h"
#include <WiFi.h>

// =========================
// WiFi
// =========================
const char* ssid = "TINKER";
const char* password = "11102006";

// =========================
// AI Thinker ESP32-CAM pins
// =========================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

WiFiServer server(80);
WiFiServer streamServer(81);

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("ESP32-CAM Starting...");

  // =========================
  // Camera configuration
  // =========================
  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Lower resolution = better for Python processing
  config.frame_size = FRAMESIZE_QVGA;   // 320x240
  config.jpeg_quality = 12;
  config.fb_count = 2;

  // =========================
  // Start camera
  // =========================
  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    return;
  }

  Serial.println("Camera initialized!");

  // =========================
  // WiFi
  // =========================
  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi Connected!");

  Serial.print("ESP32-CAM IP: ");
  Serial.println(WiFi.localIP());

  server.begin();
  streamServer.begin();

  Serial.println();
  Serial.println("==============================");
  Serial.println("ESP32-CAM READY");
  Serial.println("==============================");

  Serial.print("Web page: http://");
  Serial.println(WiFi.localIP());

  Serial.print("Stream: http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/stream");
}

// =========================
// Normal webpage
// =========================
void handleWebPage(WiFiClient &client) {

  String html = "";

  html += "HTTP/1.1 200 OK\r\n";
  html += "Content-Type: text/html\r\n";
  html += "Connection: close\r\n";
  html += "\r\n";

  html += "<!DOCTYPE html>";
  html += "<html>";
  html += "<head>";
  html += "<title>ESP32-CAM Live Stream</title>";
  html += "</head>";

  html += "<body style='background:#111;color:white;text-align:center;'>";
  html += "<h2>ESP32-CAM Live Stream</h2>";

  html += "<img src='http://";
  html += WiFi.localIP().toString();
  html += ":81/stream' width='640'>";

  html += "</body>";
  html += "</html>";

  client.print(html);
}

// =========================
// MJPEG stream
// =========================
void handleStream(WiFiClient &client) {

  client.print(
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
    "Cache-Control: no-cache\r\n"
    "Access-Control-Allow-Origin: *\r\n"
    "Connection: close\r\n"
    "\r\n"
  );

  while (client.connected()) {

    camera_fb_t *fb = esp_camera_fb_get();

    if (!fb) {
      Serial.println("Camera capture failed");
      break;
    }

    client.print("--frame\r\n");
    client.print("Content-Type: image/jpeg\r\n");
    client.print("Content-Length: ");
    client.print(fb->len);
    client.print("\r\n\r\n");

    client.write(fb->buf, fb->len);

    client.print("\r\n");

    esp_camera_fb_return(fb);

    delay(30);
  }

  client.stop();
}

// =========================
// Main loop
// =========================
void loop() {

  // Normal webpage
  WiFiClient client = server.available();

  if (client) {

    String request = client.readStringUntil('\r');

    Serial.println(request);

    if (request.indexOf("GET / ") >= 0) {
      handleWebPage(client);
    }

    delay(1);
    client.stop();
  }

  // Stream server
  WiFiClient streamClient = streamServer.available();

  if (streamClient) {

    String request = streamClient.readStringUntil('\r');

    Serial.println("Stream request:");
    Serial.println(request);

    if (request.indexOf("GET /stream") >= 0) {
      handleStream(streamClient);
    }

    streamClient.stop();
  }
}