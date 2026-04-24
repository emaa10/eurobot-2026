#include <Arduino.h>
#include "robot.h"

// Taktik-Deklaration (implementiert in tactic.cpp)
void runTactic();

// ── Core 0: ToF-Sensor-Loop ───────────────────────────────────
void setup() {
    Serial.begin(115200);
    sleep_ms(1000);
    robotInitTof();
    Serial.println("Core0: ToF bereit");
}

void loop() {
    robotPollTof();
    sleep_ms(20); // 50 Hz
}

// ── Core 1: Taktik ────────────────────────────────────────────
void setup1() {
    robotInitMotors();
    sleep_ms(2000); // warten bis Core0 ToF initialisiert hat
    Serial.println("Core1: Motoren bereit, starte Taktik");
}

void loop1() {
    runTactic();
    Serial.println("Taktik fertig.");
    while (true) sleep_ms(1000); // einmal ausführen
}
