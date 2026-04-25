// =============================================================================
// SIMA2 – Einstiegspunkt
// Core 0: ToF-Sensorloop (50 Hz), setzt opponent_detected
// Core 1: LED an → Zugschnur warten → LED aus → Taktik ausführen
// =============================================================================

#include <Arduino.h>
#include "pico/stdlib.h"
#include "robot.h"

#define PIN_PULLCORD  21
#define PIN_LED       25   // onboard LED

// ── Core 0 ───────────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    sleep_ms(500);
    robotInitTof();
    Serial.println("Core0: ToF bereit");
}

void loop() {
    robotPollTof();   // liest beide VL53L0X, aktualisiert opponent_detected
    sleep_ms(20);     // 50 Hz
}

// ── Core 1 ───────────────────────────────────────────────────────────────────

void setup1() {
    robotInitMotors();

    gpio_init(PIN_LED);
    gpio_set_dir(PIN_LED, GPIO_OUT);
    gpio_put(PIN_LED, 0);   // LED an: bereit, warte auf Zugschnur

    gpio_init(PIN_PULLCORD);
    gpio_set_dir(PIN_PULLCORD, GPIO_IN);
    gpio_pull_up(PIN_PULLCORD);

    sleep_ms(2000);  // warten bis Core0 ToF initialisiert hat

    Serial.println("Core1: bereit, warte auf Zugschnur...");
    int last_state = -1;
    int low_count = 0;
    while (true) {
        int state = gpio_get(PIN_PULLCORD);
        if (state != last_state) {
            Serial.printf("[PULLCORD] GP%d = %d (%s)\n", PIN_PULLCORD, state, state ? "HIGH / offen" : "LOW / verbunden");
            last_state = state;
        }
        if (state == 0) low_count++;
        else            low_count = 0;
        if (low_count >= 5) break;  // 5x LOW in Folge = stabil verbunden
        sleep_ms(10);
    }

    gpio_put(PIN_LED, 0);
    Serial.println("Core1: Zugschnur stabil LOW, starte Taktik");
    Serial.flush();
}

void loop1() {
    runTactic();
    while (true) sleep_ms(1000);  // runTactic() kehrt nie zurück, aber sicher ist sicher
}
