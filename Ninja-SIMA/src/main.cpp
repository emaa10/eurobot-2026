// =============================================================================
// Ninja-SIMA – Antriebssteuerung
// Arduino Uno + Waveshare STS-Servos + HC-SR04 Ultraschall + Zugschnur
// =============================================================================
//
// Pinbelegung:
//   D0/D1  Motorboard UART (TX/RX)
//   D4     HC-SR04 Echo
//   D5     HC-SR04 Trig
//   D10    Zugschnur (→ GND)
//
// Ablauf:
//   1. Warten bis Zugschnur gezogen wird (D10 LOW → HIGH)
//   2. 1 m geradeaus fahren
//   3. Bei Hindernis < 10 cm sofort stoppen
//
// Kalibrierung:
//   DRIVE_1M_MS anpassen bis der Roboter genau 1 m fährt
// =============================================================================

#include <Arduino.h>

// --- Pins -------------------------------------------------------------------
#define PIN_ECHO      4
#define PIN_TRIG      5
#define PIN_PULLCORD  10

// --- Servo-IDs --------------------------------------------------------------
#define ID_LEFT   4
#define ID_RIGHT  5

// --- Kalibrierung -----------------------------------------------------------
#define SPEED             800   // 0–1000
#define ACCELERATION      50
#define DRIVE_1M_MS       2000  // Fahrzeit für ~1 m in ms
#define STOP_DISTANCE_CM  10

// ----------------------------------------------------------------------------

// Sendet einen Waveshare/Feetech STS Rad-Modus Befehl über Hardware-Serial
void stsWriteSpeed(uint8_t id, int16_t speed, uint8_t acc) {
    uint8_t speedL = speed & 0xFF;
    uint8_t speedH = (speed >> 8) & 0xFF;
    if (speed < 0) speedH |= 0x04;

    uint8_t buf[] = {
        0xFF, 0xFF, id, 0x08, 0x03, 0x2E,
        acc, speedL, speedH, 0x00, 0x00
    };

    uint8_t checksum = 0;
    for (uint8_t i = 2; i < sizeof(buf); i++) checksum += buf[i];
    checksum = ~checksum;

    Serial.write(buf, sizeof(buf));
    Serial.write(checksum);
}

// Misst Distanz per HC-SR04, gibt cm zurück (-1 bei Timeout)
int measureDistanceCm() {
    digitalWrite(PIN_TRIG, LOW);
    delayMicroseconds(2);
    digitalWrite(PIN_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_TRIG, LOW);

    long duration = pulseIn(PIN_ECHO, HIGH, 30000);
    if (duration == 0) return -1;
    return duration / 58;
}

void stopMotors() {
    stsWriteSpeed(ID_LEFT,  0, ACCELERATION);
    stsWriteSpeed(ID_RIGHT, 0, ACCELERATION);
}

// Fährt durationMs vorwärts, bricht bei Hindernis < STOP_DISTANCE_CM ab
void driveForward(unsigned long durationMs) {
    stsWriteSpeed(ID_LEFT,   SPEED, ACCELERATION);
    stsWriteSpeed(ID_RIGHT, -SPEED, ACCELERATION);

    unsigned long start = millis();
    while (millis() - start < durationMs) {
        int dist = measureDistanceCm();
        if (dist > 0 && dist < STOP_DISTANCE_CM) {
            stopMotors();
            return;
        }
        delay(20);
    }

    stopMotors();
}

// ----------------------------------------------------------------------------

void setup() {
    pinMode(LED_BUILTIN, OUTPUT);
    Serial.begin(115200);

    pinMode(PIN_TRIG,     OUTPUT);
    pinMode(PIN_ECHO,     INPUT);
    pinMode(PIN_PULLCORD, INPUT_PULLUP);

    // Langsam blinken = warte auf Zugschnur
    while (digitalRead(PIN_PULLCORD) == LOW) {
        digitalWrite(LED_BUILTIN, HIGH); delay(500);
        digitalWrite(LED_BUILTIN, LOW);  delay(500);
    }

    // Schnell blinken = Zugschnur erkannt, fahre los
    for (int i = 0; i < 6; i++) {
        digitalWrite(LED_BUILTIN, HIGH); delay(100);
        digitalWrite(LED_BUILTIN, LOW);  delay(100);
    }

    driveForward(DRIVE_1M_MS);
}

void loop() {}
