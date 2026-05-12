#include "tests.h"
#include "test_config.h"
#include "hw_config.h"
#include "shared_state.h"
#include "tof.h"
#include "debug.h"

#include <Arduino.h>
#include <Servo.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include <math.h>

// ── Servo-Instanz (nur in diesem TU verwendet) ────────────
static Servo g_servo;

// ─────────────────────────────────────────────────────────
//  Interne Hilfsfunktion: Schritte mit Rampe fahren
// ─────────────────────────────────────────────────────────
static void run_steps(uint32_t steps) {
    float    delay_us    = DELAY_START_US;
    uint32_t decel_start = (steps > 80) ? (steps - 80) : 0;
    uint32_t log_every   = steps / 4;
    if (log_every == 0) log_every = 1;

    for (uint32_t i = 0; i < steps; ++i) {
        // Rampe hoch
        if (i < steps / 2 && delay_us > DELAY_MIN_US)
            delay_us = fmaxf(delay_us - RAMP_US, DELAY_MIN_US);
        // Rampe runter
        if (i >= decel_start && delay_us < DELAY_START_US)
            delay_us = fminf(delay_us + RAMP_US, DELAY_START_US);

        gpio_put(L_STEP, 1); sleep_us(30); gpio_put(L_STEP, 0);
        gpio_put(R_STEP, 1); sleep_us(30); gpio_put(R_STEP, 0);
        sleep_us(static_cast<uint32_t>(delay_us));

        if (i % log_every == 0)
            Serial.printf("  [step] %u/%u  delay=%.0f us\n", i + 1, steps, delay_us);
    }
}

// ─────────────────────────────────────────────────────────
//  TEST 1 — LED
// ─────────────────────────────────────────────────────────
void test_led() {
    dbg_sep("LED  GP25");

    gpio_init(PIN_LED);
    gpio_set_dir(PIN_LED, GPIO_OUT);
    dbg_info("Blinkt 6× — bitte visuell prüfen");

    for (int i = 0; i < 6; ++i) {
        gpio_put(PIN_LED, 1);
        Serial.printf("  [LED] AN  (%d/6)\n", i + 1);
        sleep_ms(250);
        gpio_put(PIN_LED, 0);
        Serial.printf("  [LED] AUS (%d/6)\n", i + 1);
        sleep_ms(250);
    }

    dbg_ok("LED-Blitztest fertig");
}

// ─────────────────────────────────────────────────────────
//  TEST 2 — PULLCORD
// ─────────────────────────────────────────────────────────
void test_pullcord() {
    dbg_sep("PULLCORD  GP21");

    gpio_init(PIN_PULLCORD);
    gpio_set_dir(PIN_PULLCORD, GPIO_IN);
    gpio_pull_down(PIN_PULLCORD);

    dbg_info("Lese GP21 für 4 s  (Kabel ziehen zum Testen)");

    bool saw_high = false;
    bool saw_low  = false;

    for (int i = 0; i < 40; ++i) {
        const int s = gpio_get(PIN_PULLCORD);
        Serial.printf("  [PULLCORD] %2d/40  GP21=%d  %s\n",
                      i + 1, s,
                      s ? "HIGH — Schnur eingesteckt / offen"
                        : "LOW  — Schnur gezogen / GND");
        if (s) saw_high = true;
        else   saw_low  = true;
        sleep_ms(100);
    }

    saw_high ? dbg_ok("HIGH-Pegel erkannt")
             : dbg_info("Kein HIGH — Pin prüfen oder Pull-Up fehlt");
    saw_low  ? dbg_ok("LOW-Pegel erkannt")
             : dbg_info("Kein LOW  — Kabel während Test abziehen");
}

// ─────────────────────────────────────────────────────────
//  TEST 3 — TOF-SENSOREN
// ─────────────────────────────────────────────────────────
void test_tof() {
    dbg_sep("TOF-SENSOREN  VL53L0X  L=i2c1(GP2/3)  R=i2c0(GP12/13)");

    // I2C-Ping
    const bool ok_l = tof_ping(i2c1);
    const bool ok_r = tof_ping(i2c0);
    Serial.printf("  [I2C] Links  (i2c1) Ping: %s\n",
                  ok_l ? "ACK OK" : "KEIN ACK — Sensor nicht verbunden?");
    Serial.printf("  [I2C] Rechts (i2c0) Ping: %s\n",
                  ok_r ? "ACK OK" : "KEIN ACK — Sensor nicht verbunden?");

    if (!ok_l && !ok_r) {
        dbg_fail("Beide Sensoren nicht erreichbar — Abbruch");
        return;
    }

    dbg_info("Starte %d Messzyklen (20 ms Abstand ≈ 50 Hz)...", TOF_SAMPLES);

    MedianFilter fl, fr;
    uint32_t l_sum = 0, r_sum = 0;
    uint16_t l_min = 9999, l_max = 0;
    uint16_t r_min = 9999, r_max = 0;
    int      l_valid = 0, r_valid = 0;

    for (int i = 0; i < TOF_SAMPLES; ++i) {
        const uint16_t rl = tof_read_raw(i2c1);
        const uint16_t rr = tof_read_raw(i2c0);
        fl.push(rl);
        fr.push(rr);

        const uint16_t dl = fl.median();
        const uint16_t dr = fr.median();
        const bool     vl = tof_valid(dl);
        const bool     vr = tof_valid(dr);

        Serial.printf("  [TOF] %2d/%d  L=%4u mm %-8s  R=%4u mm %-8s  raw(L=%u R=%u)\n",
                      i + 1, TOF_SAMPLES,
                      dl, vl ? "[OK]" : "[INVAL]",
                      dr, vr ? "[OK]" : "[INVAL]",
                      rl, rr);

        if (vl) {
            ++l_valid;
            l_sum += dl;
            l_min  = (dl < l_min) ? dl : l_min;
            l_max  = (dl > l_max) ? dl : l_max;
        }
        if (vr) {
            ++r_valid;
            r_sum += dr;
            r_min  = (dr < r_min) ? dr : r_min;
            r_max  = (dr > r_max) ? dr : r_max;
        }
        sleep_ms(20);
    }

    // Auswertung Links
    Serial.println();
    dbg_info("--- Links  ---  gültig %d/%d", l_valid, TOF_SAMPLES);
    if (l_valid > 0) {
        dbg_info("  Ø %u mm   Min %u mm   Max %u mm",
                 static_cast<uint16_t>(l_sum / l_valid), l_min, l_max);
        dbg_ok("Linker ToF liefert Messwerte");
    } else {
        dbg_fail("Linker ToF: keine gültigen Werte");
    }

    // Auswertung Rechts
    dbg_info("--- Rechts ---  gültig %d/%d", r_valid, TOF_SAMPLES);
    if (r_valid > 0) {
        dbg_info("  Ø %u mm   Min %u mm   Max %u mm",
                 static_cast<uint16_t>(r_sum / r_valid), r_min, r_max);
        dbg_ok("Rechter ToF liefert Messwerte");

        const uint16_t last_r  = fr.median();
        const bool     stopp   = tof_valid(last_r) && last_r < STOP_MM;
        dbg_info("Stopp-Schwelle %u mm: Objekt %s (%u mm)",
                 STOP_MM, stopp ? "ERKANNT" : "nicht erkannt", last_r);
    } else {
        dbg_fail("Rechter ToF: keine gültigen Werte");
    }
}

// ─────────────────────────────────────────────────────────
//  TEST 4 — STEPPER-MOTOREN
// ─────────────────────────────────────────────────────────
void test_motors() {
    dbg_sep("STEPPER-MOTOREN");

    struct Move {
        const char *label;
        bool        l_dir;
        bool        r_dir;
        uint32_t    steps;
    };

    const uint32_t steps_d =
        static_cast<uint32_t>(MOTOR_TEST_CM  * 10.0f * STEPS_PER_MM);
    const uint32_t steps_t =
        static_cast<uint32_t>(MOTOR_TEST_DEG * STEPS_PER_DEG);

    const Move moves[] = {
        { "VORWAERTS  ", true,  false, steps_d },
        { "RUECKWAERTS", false, true,  steps_d },
        { "RECHTS (+) ", true,  true,  steps_t },
        { "LINKS  (-) ", false, false, steps_t },
    };

    for (const auto &m : moves) {
        dbg_info("%s → %u Schritte", m.label, m.steps);
        gpio_put(L_DIR, m.l_dir ? 1 : 0);
        gpio_put(R_DIR, m.r_dir ? 1 : 0);
        MOTORS_ON();
        Serial.printf("  [motor] L_DIR=%d  R_DIR=%d  Motoren EIN\n",
                      m.l_dir, m.r_dir);
        run_steps(m.steps);
        MOTORS_OFF();
        Serial.printf("  [motor] Motoren AUS\n");
        dbg_ok(m.label);
        sleep_ms(400);
    }

    dbg_ok("Motortest abgeschlossen — Bewegung visuell prüfen");
}

// ─────────────────────────────────────────────────────────
//  TEST 5 — SERVO
// ─────────────────────────────────────────────────────────
void test_servo() {
    dbg_sep("SERVO  GP28");

    g_servo.attach(PIN_SERVO);
    dbg_info("Servo angehängt an GP%u", PIN_SERVO);

    const int sweep[] = { 0, 45, 90, 135, 180, 90, 0 };

    dbg_info("Sweep 0→45→90→135→180→90→0°  (%d Zyklen)", SERVO_CYCLES);
    for (int c = 0; c < SERVO_CYCLES; ++c) {
        for (int p : sweep) {
            g_servo.write(p);
            Serial.printf("  [SERVO] Zyklus %d/%d  → %3d°\n",
                          c + 1, SERVO_CYCLES, p);
            delay(500);
        }
    }

    dbg_info("Simuliere servoSpin() — 6 Halbzyklen 90°↔0°");
    for (int i = 0; i < 6; ++i) {
        g_servo.write(90);
        Serial.printf("  [SERVO] spin → 90°  (%d/6)\n", i + 1);
        delay(500);
        g_servo.write(0);
        Serial.printf("  [SERVO] spin →  0°  (%d/6)\n", i + 1);
        delay(500);
    }

    g_servo.write(90);
    delay(300);
    g_servo.detach();
    dbg_ok("Servotest abgeschlossen");
}

// ─────────────────────────────────────────────────────────
//  TEST 6 — STOPP-LOGIK  (rechter ToF + Motorpause)
// ─────────────────────────────────────────────────────────
void test_stopp_logik() {
    dbg_sep("STOPP-LOGIK  (rechter ToF + Motorpause)");
    dbg_info("Roboter fährt %d cm vorwaerts.", MOTOR_TEST_CM * 2);
    dbg_info("Objekt vor RECHTEN Sensor halten → Motor pausiert.");
    dbg_info("Objekt wegnehmen → Motor faehrt weiter.");

    const uint32_t steps =
        static_cast<uint32_t>(MOTOR_TEST_CM * 2 * 10.0f * STEPS_PER_MM);

    gpio_put(L_DIR, 1);
    gpio_put(R_DIR, 0);
    MOTORS_ON();

    float    delay_us    = DELAY_START_US;
    uint32_t decel_start = (steps > 80) ? (steps - 80) : 0;
    uint32_t paused_ms   = 0;
    bool     was_paused  = false;

    for (uint32_t i = 0; i < steps; ) {
        const uint16_t dr  = last_dist_r;          // aus Core-0-Shared-State
        const bool     obs = tof_valid(dr) && dr < STOP_MM;

        if (obs) {
            if (!was_paused) {
                MOTORS_OFF();
                Serial.printf("  [STOPP ] Schritt %u — Hindernis %u mm < %u mm\n",
                              i, dr, STOP_MM);
                was_paused = true;
            }
            sleep_ms(20);
            paused_ms += 20;
            if (paused_ms >= STOPP_TIMEOUT_MS) {
                dbg_fail("Stopp-Timeout erreicht — Fahrt abgebrochen");
                MOTORS_OFF();
                return;
            }
            continue;           // i nicht erhöhen — Schritt nachholen
        }

        if (was_paused) {
            Serial.printf("  [RESUME] Weg frei nach %.1f s Pause  (R=%u mm)\n",
                          paused_ms / 1000.0f, dr);
            MOTORS_ON();
            was_paused = false;
            paused_ms  = 0;
        }

        // Rampe hoch
        if (i < steps / 2 && delay_us > DELAY_MIN_US)
            delay_us = fmaxf(delay_us - RAMP_US, DELAY_MIN_US);
        // Rampe runter
        if (i >= decel_start && delay_us < DELAY_START_US)
            delay_us = fminf(delay_us + RAMP_US, DELAY_START_US);

        gpio_put(L_STEP, 1); sleep_us(30); gpio_put(L_STEP, 0);
        gpio_put(R_STEP, 1); sleep_us(30); gpio_put(R_STEP, 0);
        sleep_us(static_cast<uint32_t>(delay_us));

        if (i % 60 == 0)
            Serial.printf("  [fahrt ] step=%u/%u  R=%u mm  delay=%.0f us\n",
                          i, steps, dr, delay_us);
        ++i;
    }

    MOTORS_OFF();
    dbg_ok("Stopp-Logik-Test abgeschlossen");
}
