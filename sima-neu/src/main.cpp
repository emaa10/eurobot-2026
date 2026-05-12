#include <Arduino.h>

#define PIN_PULLCORD 21

void waitForPullcord() {
    gpio_init(PIN_PULLCORD);
    gpio_set_dir(PIN_PULLCORD, GPIO_IN);
    gpio_pull_down(PIN_PULLCORD);  // Ruhezustand = HIGH, gezogen = LOW

    Serial.println("[PULLCORD] warte auf Schnur...");

    static int stable_state = 1;

    while (true) {
        int count = 0;
        for (int i = 0; i < 5; i++) {
            count += gpio_get(PIN_PULLCORD);
            sleep_ms(10);
        }
        int new_state = (count >= 3) ? 1 : 0;

        if (new_state != stable_state) {
            stable_state = new_state;
            Serial.printf("[PULLCORD] WECHSEL -> %d  (%s)\n",
                          stable_state,
                          stable_state ? "HIGH - Schnur eingesteckt" : "LOW  - Schnur gezogen");
        } else {
            Serial.printf("[PULLCORD] GP%d = %d  (%s)\n",
                          PIN_PULLCORD, stable_state,
                          stable_state ? "HIGH - Schnur eingesteckt" : "LOW  - Schnur gezogen");
        }

        if (stable_state == 0) {
            Serial.println("[PULLCORD] Schnur gezogen — starte");
            return;
        }

        sleep_ms(150);
    }
}

void setup() {
    Serial.begin(115200);
    waitForPullcord();
}

void loop() {
    // Taktik hier
    delay(1000);
}