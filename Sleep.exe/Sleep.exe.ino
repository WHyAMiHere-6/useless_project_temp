#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// =============== WIFI ===============

#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "Galaxy S24";
const char* password = "11102006";

WebServer server(80);


// ================= OLED =================

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

Adafruit_SSD1306 display(
  SCREEN_WIDTH,
  SCREEN_HEIGHT,
  &Wire,
  OLED_RESET
);


// ================= PINS =================

#define RED_LED 18
#define BLUE_LED 19
#define BUZZER 25
#define BUTTON 4


// ================= FUNCTION DECLARATIONS =================

void wakeUpMode();
void handleRoot();
void handleAlert();


// ================= WEB SERVER FUNCTIONS =================

// Home page

void handleRoot() {

  server.send(
    200,
    "text/plain",
    "Drowsiness Alert ESP32 is running"
  );
}


// Alert endpoint

void handleAlert() {

  Serial.println("DROWSINESS ALERT RECEIVED!");

  // Activate your existing wake-up alarm
  wakeUpMode();

  server.send(
    200,
    "text/plain",
    "ALERT ACTIVATED"
  );
}


// ================= SETUP =================

void setup() {

  Serial.begin(115200);


  // LEDs

  pinMode(RED_LED, OUTPUT);
  pinMode(BLUE_LED, OUTPUT);


  // Buzzer

  pinMode(BUZZER, OUTPUT);


  // Push button

  pinMode(BUTTON, INPUT_PULLUP);


  // I2C for OLED

  Wire.begin(21, 22);


  // Start OLED

  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {

    Serial.println("OLED not found!");

    while (true);
  }


  // Initial outputs

  digitalWrite(RED_LED, LOW);
  digitalWrite(BLUE_LED, HIGH);


  // OLED startup screen

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(2);

  display.setCursor(15, 10);
  display.println("SLEEP");

  display.setCursor(25, 35);
  display.println("MODE");

  display.display();


  delay(1000);


  // ================= WIFI CONNECTION =================

  Serial.println();
  Serial.print("Connecting to WiFi: ");

  Serial.println(ssid);

  WiFi.begin(ssid, password);


  while (WiFi.status() != WL_CONNECTED) {

    delay(500);

    Serial.print(".");
  }


  Serial.println();
  Serial.println("WiFi Connected!");

  Serial.print("ESP32 IP Address: ");

  Serial.println(WiFi.localIP());


  // ================= WEB SERVER =================

  server.on("/", handleRoot);

  server.on("/alert", handleAlert);


  server.begin();


  Serial.println("Web Server Started!");
  Serial.println("Ready for Drowsiness Alerts!");
}


// ================= MAIN LOOP =================

void loop() {

  // Listen for requests from Python/laptop

  server.handleClient();


  // Read button

  int buttonState = digitalRead(BUTTON);


  // ================= BUTTON PRESSED =================

  if (buttonState == LOW) {

    Serial.println("BUTTON PRESSED - WAKE UP MODE");

    wakeUpMode();


    // Wait until button is released

    while (digitalRead(BUTTON) == LOW) {

      server.handleClient();

      delay(10);
    }


    delay(300);
  }


  // ================= NORMAL SLEEP MODE =================

  else {

    digitalWrite(BLUE_LED, HIGH);

    digitalWrite(RED_LED, LOW);
  }
}


// ================= WAKE UP MODE =================

void wakeUpMode() {

  Serial.println("WAKE UP MODE ACTIVATED!");


  // LEDs

  digitalWrite(BLUE_LED, LOW);

  digitalWrite(RED_LED, HIGH);


  // OLED

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);


  display.setTextSize(2);

  display.setCursor(15, 5);

  display.println("WAKE UP!");


  display.setTextSize(1);

  display.setCursor(10, 40);

  display.println("Alarm Activated");


  display.display();


  // ================= PASSIVE BUZZER ALARM =================
  // Pitch continuously increases

  for (int frequency = 800;
       frequency <= 3000;
       frequency += 100) {

    tone(BUZZER, frequency);

    delay(70);
  }


  // Pitch continuously decreases

  for (int frequency = 3000;
       frequency >= 800;
       frequency -= 100) {

    tone(BUZZER, frequency);

    delay(70);
  }


  noTone(BUZZER);


  delay(500);
}
