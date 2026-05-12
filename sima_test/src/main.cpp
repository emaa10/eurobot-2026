// ╔══════════════════════════════════════════════════════════════════╗
// ║   EUROBOT SIMA — Vollständiger Komponenten-Test (PlatformIO)   ║
// ║                                                                 ║
// ║   Core0  →  ToF-Dauerschleife (füllt shared state)            ║
// ║   Core1  →  Testsequenz (LED, Pullcord, ToF, Motor, Servo)     ║
// ╚══════════════════════════════════════════════════════════════════╝

#include <Arduino.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"

#include "hw_config.h"
#include "test_config.h"
#include "shared_state.h"
#include "tof.h"
#include "tests.h"
#include "debug.h"

// ── Shared State Definitions (hier allokiert) ─────────────────────
volatile bool     opponent_detected = false;
volatile uint16_t last_dist_l       = 9999;
volatile uint16_t last_dist_r       = 9999;

// ═════════════════════════════════════════════════════════════════
//  CORE 0 — I2C-Init + ToF-Dauerschleife
// ═════════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    sleep_ms(600);

    Serial.println();
    Serial.println(F("╔══════════════════════════════════════════════╗"));
    Serial.println(F("║   EUROBOT SIMA — KOMPONENTEN-TEST            ║"));
    Serial.println(F("║   Core0: I2C + ToF-Init                      ║"));
    Serial.println(F("╚══════════════════════════════════════════════╝"));

    // i2c1 → GP2 (SDA) / GP3 (SCL) → Linker Sensor
    Serial.println(F("[Core0] I2C1 init (GP2/GP3)..."));
    i2c_init(i2c1, 100'000);
    gpio_set_function(2, GPIO_FUNC_I2C); gpio_pull_up(2);
    gpio_set_function(3, GPIO_FUNC_I2C); gpio_pull_up(3);

    // i2c0 → GP12 (SDA) / GP13 (SCL) → Rechter Sensor
    Serial.println(F("[Core0] I2C0 init (GP12/GP13)..."));
    i2c_init(i2c0, 100'000);
    gpio_set_function(12, GPIO_FUNC_I2C); gpio_pull_up(12);
    gpio_set_function(13, GPIO_FUNC_I2C); gpio_pull_up(13);

    tof_start(i2c1);
    tof_start(i2c0);
    Serial.println(F("[Core0] ToF bereit — Dauerschleife läuft"));
}

void loop() {
    // Rohmesswerte in Median-Filter schreiben
    filter_l.push(tof_read_raw(i2c1));
    filter_r.push(tof_read_raw(i2c0));

    const uint16_t d1 = filter_l.median();
    const uint16_t d2 = filter_r.median();
    last_dist_l = d1;
    last_dist_r = d2;

    const bool obs = tof_valid(d2) && d2 < STOP_MM;

    // Statusänderung loggen
    if (obs != opponent_detected) {
        opponent_detected = obs;
        Serial.printf("[Core0] opponent=%d  L=%u mm  R=%u mm\n",
                      static_cast<int>(opponent_detected), d1, d2);
    }

    sleep_ms(20);   // 50 Hz
}

// ═════════════════════════════════════════════════════════════════
//  CORE 1 — Testsequenz
// ═════════════════════════════════════════════════════════════════

void setup1() {
    // Motor-GPIOs konfigurieren
    const uint motor_pins[] = { L_STEP, L_DIR, L_EN, R_STEP, R_DIR, R_EN };
    for (uint p : motor_pins) {
        gpio_init(p);
        gpio_set_dir(p, GPIO_OUT);
    }
    MOTORS_OFF();

    sleep_ms(2500);     // Core0 Zeit zum Starten lassen

    Serial.println();
    Serial.println(F("╔══════════════════════════════════════════════╗"));
    Serial.println(F("║   EUROBOT SIMA — KOMPONENTEN-TEST            ║"));
    Serial.println(F("║   Core1: Testsequenz                          ║"));
    Serial.println(F("╠══════════════════════════════════════════════╣"));
    Serial.printf ("║  LED          : %-3s                          ║\n",
                   TEST_LED      ? "AN" : "AUS");
    Serial.printf ("║  PULLCORD     : %-3s                          ║\n",
                   TEST_PULLCORD ? "AN" : "AUS");
    Serial.printf ("║  TOF          : %-3s                          ║\n",
                   TEST_TOF      ? "AN" : "AUS");
    Serial.printf ("║  MOTOREN      : %-3s                          ║\n",
                   TEST_MOTORS   ? "AN" : "AUS");
    Serial.printf ("║  SERVO        : %-3s                          ║\n",
                   TEST_SERVO    ? "AN" : "AUS");
    Serial.printf ("║  STOPP-LOGIK  : %-3s                          ║\n",
                   TEST_STOPP    ? "AN" : "AUS");
    Serial.println(F("╚══════════════════════════════════════════════╝"));
    sleep_ms(800);
}

void loop1() {
    static bool done = false;
    if (done) { sleep_ms(1000); return; }
    done = true;

    // ── Tests ausführen ───────────────────────────────────────────
#if TEST_LED
    test_led();
    sleep_ms(600);
#endif

#if TEST_PULLCORD
    test_pullcord();
    sleep_ms(600);
#endif

#if TEST_TOF
    test_tof();
    sleep_ms(600);
#endif

#if TEST_MOTORS
    test_motors();
    sleep_ms(600);
#endif

#if TEST_SERVO
    test_servo();
    sleep_ms(600);
#endif

#if TEST_STOPP
    test_stopp_logik();
    sleep_ms(600);
#endif

    // ── Abschluss-Banner ──────────────────────────────────────────
    Serial.println();
    Serial.println(F("╔══════════════════════════════════════════════╗"));
    Serial.println(F("║   ALLE TESTS ABGESCHLOSSEN                   ║"));
    Serial.println(F("║   Konsole auf [FAIL] Eintraege prüfen.       ║"));
    Serial.println(F("║   Onboard-LED blinkt schnell = fertig.       ║"));
    Serial.println(F("╚══════════════════════════════════════════════╝"));

    // Schnelles Abschluss-Blinken
    gpio_init(PIN_LED);
    gpio_set_dir(PIN_LED, GPIO_OUT);
    for (int i = 0; i < 14; ++i) {
        gpio_put(PIN_LED, i % 2);
        sleep_ms(70);
    }
    gpio_put(PIN_LED, 0);
}
