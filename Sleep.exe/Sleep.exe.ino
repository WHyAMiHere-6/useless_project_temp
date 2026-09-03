#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include <WiFi.h>
#include <WebServer.h>


// ============================================================
// WIFI
// ============================================================

const char* ssid = "TINKER";
const char* password = "11102006";

WebServer server(80);


// ============================================================
// OLED
// ============================================================

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


// ============================================================
// PINS
// ============================================================

#define RED_LED 18
#define BLUE_LED 19
#define BUZZER 25
#define BUTTON 4


// ============================================================
// ALARM STATE
// ============================================================

bool alarmActive = false;


// ============================================================
// SOOTHING BUZZER SETTINGS
// ============================================================
//
// Instead of a harsh 800 -> 3000 Hz sweep,
// we use a gentle two-tone/pulse pattern.
//
// The frequency stays in a comfortable range and
// changes slowly.
//
// ============================================================

unsigned long lastBuzzerChange = 0;

bool buzzerPhase = false;

const unsigned long BUZZER_ON_TIME = 180;
const unsigned long BUZZER_OFF_TIME = 520;

// Soft frequency
const int SOFT_FREQUENCY_1 = 650;
const int SOFT_FREQUENCY_2 = 800;


// ============================================================
// EMERGENCY LED SETTINGS
// ============================================================

unsigned long lastLEDChange = 0;

bool redActive = false;

const unsigned long LED_BLINK_TIME = 350;


// ============================================================
// FUNCTION DECLARATIONS
// ============================================================

void wakeUpMode();
void stopAlarm();

void updateBuzzer();
void updateLEDs();

void sleepMode();

void handleRoot();
void handleAlert();
void handleStop();


// ============================================================
// SLEEPING MODE
// ============================================================
//
// While sleeping:
//
//   🔇 Buzzer OFF
//   🔴 Red OFF
//   🔵 Blue OFF
//
// Nothing is active.
// ============================================================

void sleepMode() {

  alarmActive = false;

  // Stop buzzer
  noTone(BUZZER);

  // Turn LEDs OFF
  digitalWrite(RED_LED, LOW);
  digitalWrite(BLUE_LED, LOW);

  // Reset timers
  lastBuzzerChange = millis();
  lastLEDChange = millis();

  buzzerPhase = false;
  redActive = false;


  // ----------------------------------------------------------
  // OLED
  // ----------------------------------------------------------

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(2);

  display.setCursor(15, 10);
  display.println("SLEEP");

  display.setCursor(25, 35);
  display.println("MODE");

  display.display();


  Serial.println("SLEEP MODE - ALL ALARM OUTPUTS OFF");
}


// ============================================================
// WAKE-UP / ALARM MODE
// ============================================================

void wakeUpMode() {

  // Activate alarm
  alarmActive = true;


  // Reset buzzer
  lastBuzzerChange = millis();
  buzzerPhase = false;


  // Reset LEDs
  lastLEDChange = millis();
  redActive = true;


  // ----------------------------------------------------------
  // Start with RED LED
  // ----------------------------------------------------------

  digitalWrite(RED_LED, HIGH);
  digitalWrite(BLUE_LED, LOW);


  // ----------------------------------------------------------
  // Start soft buzzer
  // ----------------------------------------------------------

  tone(
    BUZZER,
    SOFT_FREQUENCY_1
  );


  // ----------------------------------------------------------
  // OLED
  // ----------------------------------------------------------

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(2);

  display.setCursor(15, 5);

  display.println("WAKE UP!");

  display.setTextSize(1);

  display.setCursor(10, 40);

  display.println("Please wake up");

  display.display();


  Serial.println("WAKE UP MODE ACTIVATED!");
}


// ============================================================
// STOP ALARM
// ============================================================
//
// This is called by:
//
// Python -> /stop
//
// It immediately turns EVERYTHING off.
// ============================================================

void stopAlarm() {

  alarmActive = false;


  // ----------------------------------------------------------
  // BUZZER OFF
  // ----------------------------------------------------------

  noTone(BUZZER);


  // ----------------------------------------------------------
  // LEDS OFF
  // ----------------------------------------------------------

  digitalWrite(RED_LED, LOW);
  digitalWrite(BLUE_LED, LOW);


  // ----------------------------------------------------------
  // RESET VARIABLES
  // ----------------------------------------------------------

  buzzerPhase = false;
  redActive = false;

  lastBuzzerChange = millis();
  lastLEDChange = millis();


  // ----------------------------------------------------------
  // OLED
  // ----------------------------------------------------------

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(2);

  display.setCursor(15, 10);
  display.println("SLEEP");

  display.setCursor(25, 35);
  display.println("MODE");

  display.display();


  Serial.println("ALARM STOPPED");
  Serial.println("SLEEP MODE - BUZZER OFF - LEDS OFF");
}


// ============================================================
// SMOOTH / SOOTHING BUZZER
// ============================================================
//
// Pattern:
//
//   soft tone
//       ↓
//   silence
//       ↓
//   slightly higher soft tone
//       ↓
//   silence
//       ↓
//   repeat
//
// This avoids the aggressive siren effect.
// ============================================================

void updateBuzzer() {

  if (!alarmActive) {
    noTone(BUZZER);
    return;
  }


  unsigned long now = millis();


  // ----------------------------------------------------------
  // Tone ON phase
  // ----------------------------------------------------------

  if (!buzzerPhase) {

    if (
      now - lastBuzzerChange
      >= BUZZER_OFF_TIME
    ) {

      lastBuzzerChange = now;

      buzzerPhase = true;


      // Alternate between two gentle tones

      if (buzzerPhase) {

        tone(
          BUZZER,
          SOFT_FREQUENCY_2
        );
      }
    }
  }


  // ----------------------------------------------------------
  // Tone OFF phase
  // ----------------------------------------------------------

  else {

    if (
      now - lastBuzzerChange
      >= BUZZER_ON_TIME
    ) {

      lastBuzzerChange = now;

      buzzerPhase = false;

      noTone(BUZZER);
    }
  }
}


// ============================================================
// EMERGENCY LED BLINK
// ============================================================
//
// RED -> BLUE -> RED -> BLUE
//
// Smooth alternating emergency-style flash.
// ============================================================

void updateLEDs() {

  if (!alarmActive) {

    digitalWrite(RED_LED, LOW);
    digitalWrite(BLUE_LED, LOW);

    return;
  }


  unsigned long now = millis();


  if (
    now - lastLEDChange
    >= LED_BLINK_TIME
  ) {

    lastLEDChange = now;


    if (redActive) {

      // RED OFF
      digitalWrite(RED_LED, LOW);

      // BLUE ON
      digitalWrite(BLUE_LED, HIGH);

      redActive = false;
    }

    else {

      // BLUE OFF
      digitalWrite(BLUE_LED, LOW);

      // RED ON
      digitalWrite(RED_LED, HIGH);

      redActive = true;
    }
  }
}


// ============================================================
// WEB SERVER - HOME
// ============================================================

void handleRoot() {

  server.send(
    200,
    "text/plain",
    "Drowsiness Alert ESP32 is running"
  );
}


// ============================================================
// WEB SERVER - ALERT
// ============================================================

void handleAlert() {

  Serial.println(
    "DROWSINESS ALERT RECEIVED!"
  );


  wakeUpMode();


  server.send(
    200,
    "text/plain",
    "ALERT ACTIVATED"
  );
}


// ============================================================
// WEB SERVER - STOP
// ============================================================

void handleStop() {

  Serial.println(
    "STOP ALARM REQUEST RECEIVED!"
  );


  stopAlarm();


  server.send(
    200,
    "text/plain",
    "ALARM STOPPED"
  );
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);


  // ==========================================================
  // LEDS
  // ==========================================================

  pinMode(
    RED_LED,
    OUTPUT
  );

  pinMode(
    BLUE_LED,
    OUTPUT
  );


  // ==========================================================
  // BUZZER
  // ==========================================================

  pinMode(
    BUZZER,
    OUTPUT
  );

  noTone(BUZZER);


  // ==========================================================
  // BUTTON
  // ==========================================================

  pinMode(
    BUTTON,
    INPUT_PULLUP
  );


  // ==========================================================
  // OLED I2C
  // ==========================================================

  Wire.begin(
    21,
    22
  );


  // ==========================================================
  // OLED START
  // ==========================================================

  if (
    !display.begin(
      SSD1306_SWITCHCAPVCC,
      SCREEN_ADDRESS
    )
  ) {

    Serial.println(
      "OLED not found!"
    );

    while (true) {
      delay(100);
    }
  }


  // ==========================================================
  // INITIAL STATE
  // ==========================================================

  sleepMode();

  delay(1000);


  // ==========================================================
  // WIFI
  // ==========================================================

  Serial.println();

  Serial.print(
    "Connecting to WiFi: "
  );

  Serial.println(
    ssid
  );


  WiFi.begin(
    ssid,
    password
  );


  while (
    WiFi.status()
    != WL_CONNECTED
  ) {

    delay(500);

    Serial.print(".");
  }


  Serial.println();

  Serial.println(
    "WiFi Connected!"
  );


  Serial.print(
    "ESP32 IP Address: "
  );

  Serial.println(
    WiFi.localIP()
  );


  // ==========================================================
  // WEB SERVER
  // ==========================================================

  server.on(
    "/",
    handleRoot
  );


  server.on(
    "/alert",
    handleAlert
  );


  server.on(
    "/stop",
    handleStop
  );


  server.begin();


  Serial.println(
    "Web Server Started!"
  );

  Serial.println(
    "Ready for Drowsiness Alerts!"
  );

  Serial.println();

  Serial.println(
    " /alert -> ALARM ON"
  );

  Serial.println(
    " /stop  -> ALARM OFF"
  );

  Serial.println();
}


// ============================================================
// MAIN LOOP
// ============================================================

void loop() {

  // ----------------------------------------------------------
  // IMPORTANT:
  // Keep this running constantly so /stop is always received.
  // ----------------------------------------------------------

  server.handleClient();


  // ----------------------------------------------------------
  // Update alarm without delay()
  // ----------------------------------------------------------

  updateBuzzer();

  updateLEDs();


  // ==========================================================
  // BUTTON
  // ==========================================================

  int buttonState = digitalRead(
    BUTTON
  );


  if (
    buttonState == LOW
  ) {

    Serial.println(
      "BUTTON PRESSED - WAKE UP MODE"
    );


    wakeUpMode();


    // --------------------------------------------------------
    // Wait for release
    // --------------------------------------------------------

    while (
      digitalRead(BUTTON) == LOW
    ) {

      server.handleClient();

      updateBuzzer();

      updateLEDs();

      delay(10);
    }


    delay(300);
  }
}
