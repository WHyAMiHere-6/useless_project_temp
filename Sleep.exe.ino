#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

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

// ================= SETUP =================

void setup() {

  Serial.begin(115200);

  // LEDs
  pinMode(RED_LED, OUTPUT);
  pinMode(BLUE_LED, OUTPUT);

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
}


// ================= MAIN LOOP =================

void loop() {

  int buttonState = digitalRead(BUTTON);

  // Button pressed
  if (buttonState == LOW) {

    wakeUpMode();

    // Wait until button is released
    while (digitalRead(BUTTON) == LOW) {
      delay(10);
    }

    delay(300);
  }

  // Normal sleeping mode
  else {

    digitalWrite(BLUE_LED, HIGH);
    digitalWrite(RED_LED, LOW);
  }
}


// ================= WAKE UP MODE =================

void wakeUpMode() {

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


  // 🔊 Passive buzzer alarm
  // Pitch continuously changes

  for (int frequency = 800;
       frequency <= 3000;
       frequency += 100) {

    tone(BUZZER, frequency);

    delay(70);
  }


  for (int frequency = 3000;
       frequency >= 800;
       frequency -= 100) {

    tone(BUZZER, frequency);

    delay(70);
  }

  noTone(BUZZER);

  delay(500);
}
