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
    gpio_put(PIN_LED, 1);   // LED an: bereit, warte auf Zugschnur

    gpio_init(PIN_PULLCORD);
    gpio_set_dir(PIN_PULLCORD, GPIO_IN);
    gpio_pull_up(PIN_PULLCORD);

    sleep_ms(2000);  // warten bis Core0 ToF initialisiert hat

    Serial.println("Core1: bereit, warte auf Zugschnur...");
    while (gpio_get(PIN_PULLCORD) == 1) sleep_ms(10);

    gpio_put(PIN_LED, 0);   // LED aus: Zugschnur gezogen, starte Taktik
    Serial.println("Core1: Zugschnur gezogen, starte Taktik");
}

void loop1() {
    runTactic();
    while (true) sleep_ms(1000);  // runTactic() kehrt nie zurück, aber sicher ist sicher
}
