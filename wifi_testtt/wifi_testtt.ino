#include <WiFi.h>

const char* ssid = "Galaxy S24";
const char* password = "11102006";

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("=== WIFI TEST ===");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting");

  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("✅ WIFI CONNECTED!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } 
  else {
    Serial.println("❌ WIFI CONNECTION FAILED");
    Serial.print("WiFi status: ");
    Serial.println(WiFi.status());
  }
}

void loop() {
}