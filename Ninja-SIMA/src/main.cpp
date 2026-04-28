#include <SCServo.h>

SMS_STS sc;

void blink(int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_BUILTIN, HIGH); delay(150);
    digitalWrite(LED_BUILTIN, LOW);  delay(150);
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(1000000);
  sc.pSerial = &Serial;
  delay(1000);

  // Scan IDs 1–20
  for (int id = 1; id <= 20; id++) {
    if (sc.Ping(id) != -1) {
      delay(500);
      blink(id);   // LED blinkt ID-Anzahl mal
      delay(1000);
    }
  }

  // Scan fertig: 3x schnell blinken
  blink(3);
}

void loop() {}
