#include <Arduino.h>
#include <Servo.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include <math.h>

// ── Pins ─────────────────────────────────────────────────────────
#define PIN_PULLCORD  21
#define PIN_SERVO     28
#define PIN_XSHUT1    20
#define PIN_XSHUT2    19

// ── Motor ─────────────────────────────────────────────────────────
#define L_STEP  0
#define L_DIR   1
#define L_EN    7
#define R_STEP  10
#define R_DIR   9
#define R_EN    15

// Sofort keine Steps mehr, EN nach 2s aus
#define MOTORS_OFF() do { \
    digitalWrite(L_STEP, 0); digitalWrite(R_STEP, 0); \
    delay(2000); \
    gpio_put(L_EN, 1); gpio_put(R_EN, 1); \
} while(0)

#define MOTORS_ON()  do { gpio_put(L_EN, 0); gpio_put(R_EN, 0); } while(0)

// ── Kalibrierung ──────────────────────────────────────────────────
static constexpr float    STEPS_PER_MM  = 980.0f / 1000.0f;
static constexpr float    SPEED_LOW_US  = 6000.0f;   // Startintervall (µs/Step)
static constexpr float    SPEED_HIGH_US = 2000.0f;   // Maximalintervall (µs/Step)
static constexpr uint32_t ACCEL_STEPS   = 80;         // Schritte für volle Rampe

// Lineare Geschwindigkeitsrampe: k ∈ [0, ACCEL_STEPS] → Intervall in µs.
// k=0 ≙ Anfangsgeschwindigkeit, k=ACCEL_STEPS ≙ Maximalgeschwindigkeit.
// Durch Interpolation in 1/t-Raum bleibt die Beschleunigung physikalisch konstant.
static inline float rampDelay(uint32_t k) {
    if (k >= ACCEL_STEPS) return SPEED_HIGH_US;
    float t   = (float)k / (float)ACCEL_STEPS;
    float spd = (1.0f / SPEED_LOW_US) + t * (1.0f / SPEED_HIGH_US - 1.0f / SPEED_LOW_US);
    return 1.0f / spd;
}

// ── ToF ───────────────────────────────────────────────────────────
#define I2C_PORT      i2c1
#define PIN_SDA       2
#define PIN_SCL       3
#define ADDR_DEFAULT  0x29
#define ADDR_LEFT     0x30
#define ADDR_RIGHT    0x29
#define STOP_MM       200

// ── Fahrziel ──────────────────────────────────────────────────────
#define TARGET_MM     1100

// ── Zeitlimit ─────────────────────────────────────────────────────
#define MATCH_DURATION_MS  98000UL

// ═════════════════════════════════════════════════════════════════
//  Globale Zeitbasis (gesetzt beim Pullcord-Ziehen)
// ═════════════════════════════════════════════════════════════════
volatile uint32_t match_start_ms = 0;

static inline bool timeUp() {
    return (millis() - match_start_ms) >= MATCH_DURATION_MS;
}

// ═════════════════════════════════════════════════════════════════
//  Interrupt-Flag (Core1 schreibt, Core0 liest)
// ═════════════════════════════════════════════════════════════════
volatile bool opponent_detected = false;
volatile uint16_t tof_left      = 9999;
volatile uint16_t tof_right     = 9999;

// ═════════════════════════════════════════════════════════════════
//  ToF (läuft auf Core1)
// ═════════════════════════════════════════════════════════════════

struct MedianFilter {
    static constexpr uint8_t N     = 7;
    static constexpr uint8_t READY = 3;
    uint16_t buf[N];
    uint8_t  idx   = 0;
    uint8_t  count = 0;

    MedianFilter() { for (auto &v : buf) v = 9999; }

    void push(uint16_t v) {
        if (v == 9999 || v > 2000) return;
        if (v < 30)                return;
        buf[idx] = v;
        idx = (idx + 1) % N;
        if (count < N) count++;
    }

    uint16_t median() const {
        if (count < READY) return 9999;
        uint16_t tmp[N];
        for (uint8_t i = 0; i < N; i++) tmp[i] = buf[i];
        for (uint8_t i = 0; i < N-1; i++)
            for (uint8_t j = 0; j < N-1-i; j++)
                if (tmp[j] > tmp[j+1]) { uint16_t t=tmp[j]; tmp[j]=tmp[j+1]; tmp[j+1]=t; }
        return tmp[count / 2];
    }
};

static MedianFilter mf_left, mf_right;

static void tof_write(uint8_t addr, uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    i2c_write_blocking(I2C_PORT, addr, buf, 2, false);
}

static bool tof_ping(uint8_t addr) {
    uint8_t reg = 0x00;
    return i2c_write_blocking(I2C_PORT, addr, &reg, 1, false) >= 0;
}

static void tof_start(uint8_t addr) {
    tof_write(addr, 0x80, 0x01); tof_write(addr, 0xFF, 0x01);
    tof_write(addr, 0x00, 0x00); tof_write(addr, 0x91, 0x3C);
    tof_write(addr, 0x00, 0x01); tof_write(addr, 0xFF, 0x00);
    tof_write(addr, 0x80, 0x00); tof_write(addr, 0x00, 0x02);
}

static uint16_t tof_read_raw(uint8_t addr) {
    uint8_t reg = 0x1E, buf[2] = {0, 0};
    if (i2c_write_blocking(I2C_PORT, addr, &reg, 1, true) < 0) return 9999;
    i2c_read_blocking(I2C_PORT, addr, buf, 2, false);
    uint16_t v = (buf[0] << 8) | buf[1];
    if (v == 0 || v == 20 || v == 8190 || v == 9999) return 9999;
    return v;
}

static void tof_init_dual() {
    gpio_put(PIN_XSHUT1, 0); gpio_put(PIN_XSHUT2, 0);
    sleep_ms(10);

    gpio_put(PIN_XSHUT1, 1); sleep_ms(10);
    tof_write(ADDR_DEFAULT, 0x8A, ADDR_LEFT & 0x7F);
    sleep_ms(5);
    Serial.printf("[TOF] Links  0x%02X Ping: %s\n", ADDR_LEFT,  tof_ping(ADDR_LEFT)  ? "OK" : "FEHLER");
    tof_start(ADDR_LEFT);

    gpio_put(PIN_XSHUT2, 1); sleep_ms(10);
    Serial.printf("[TOF] Rechts 0x%02X Ping: %s\n", ADDR_RIGHT, tof_ping(ADDR_RIGHT) ? "OK" : "FEHLER");
    tof_start(ADDR_RIGHT);
}

// ═════════════════════════════════════════════════════════════════
//  Pullcord (Core0)
// ═════════════════════════════════════════════════════════════════

static void waitForPullcord() {
    gpio_init(PIN_PULLCORD);
    gpio_set_dir(PIN_PULLCORD, GPIO_IN);
    gpio_pull_down(PIN_PULLCORD);

    Serial.println("[PULLCORD] warte auf Schnur...");
    int stable = 1;
    while (true) {
        int count = 0;
        for (int i = 0; i < 5; i++) { count += gpio_get(PIN_PULLCORD); sleep_ms(10); }
        int new_state = (count >= 3) ? 1 : 0;
        if (new_state != stable) {
            stable = new_state;
            Serial.printf("[PULLCORD] → %s\n", stable ? "HIGH - eingesteckt" : "LOW  - gezogen");
        }
        if (stable == 0) {
            match_start_ms = millis();
            Serial.println("[PULLCORD] gezogen — los!");
            return;
        }
        sleep_ms(150);
    }
}

// ═════════════════════════════════════════════════════════════════
//  Motor (Core0)
// ═════════════════════════════════════════════════════════════════

static inline void pulse() {
    digitalWrite(L_STEP, 1); digitalWrite(R_STEP, 1);
    delayMicroseconds(750);
    digitalWrite(L_STEP, 0); digitalWrite(R_STEP, 0);
}

// Hält sofort (keine Steps), EN erst nach 2s aus
static void motorsStop() {
    for (int i = 0; i < 10000; i++) {       
        digitalWrite(L_STEP, 0); digitalWrite(R_STEP, 0);
        delayMicroseconds(200);
    }
    delay(2000);
    gpio_put(L_EN, 1); gpio_put(R_EN, 1);
}

static void driveForward(uint32_t target_mm) {
    uint32_t total_steps = (uint32_t)(target_mm * STEPS_PER_MM);
    // Symmetrische Trapez-Rampe: bei kurzen Strecken wird die Rampe proportional gestaucht
    uint32_t ramp = (total_steps / 2 < ACCEL_STEPS) ? total_steps / 2 : ACCEL_STEPS;

    gpio_put(L_DIR, 1);
    gpio_put(R_DIR, 0);
    MOTORS_ON();
    Serial.printf("[DRIVE] %u mm → %u steps, Rampe: %u\n", target_mm, total_steps, ramp);

    for (uint32_t i = 0; i < total_steps; ) {

        if (timeUp()) {
            Serial.println("[DRIVE] Zeit abgelaufen — stoppe");
            motorsStop();
            return;
        }

        if (opponent_detected) {
            digitalWrite(L_STEP, 0); digitalWrite(R_STEP, 0);
            Serial.printf("[CORE0] Gegner! L=%d R=%d mm — warte...\n", tof_left, tof_right);
            delay(2000);
            gpio_put(L_EN, 1); gpio_put(R_EN, 1);

            uint32_t waited = 2000;
            while (opponent_detected) {
                if (timeUp()) {
                    Serial.println("[DRIVE] Zeit abgelaufen — stoppe");
                    motorsStop();
                    return;
                }
                sleep_ms(20);
                waited += 20;
                if (waited >= 10000) {
                    Serial.println("[CORE0] 10s Timeout — abgebrochen");
                    motorsStop();
                    return;
                }
            }
            Serial.println("[CORE0] Weg frei — weiter");
            MOTORS_ON();
            continue;
        }

        // Trapez-Profil: Anfahren → Cruise → Bremsen (symmetrisch, konstante Beschleunigung)
        float delay_us;
        if (i < ramp) {
            delay_us = rampDelay(i * ACCEL_STEPS / ramp);
        } else if (i >= total_steps - ramp) {
            delay_us = rampDelay((total_steps - 1 - i) * ACCEL_STEPS / ramp);
        } else {
            delay_us = SPEED_HIGH_US;
        }

        pulse();
        uint32_t wait = (uint32_t)delay_us > 750u ? (uint32_t)delay_us - 750u : 0u;
        delayMicroseconds(wait);

        if (i % 300 == 0)
            Serial.printf("[DRIVE] %u/%u  L=%d R=%d mm\n", i, total_steps, tof_left, tof_right);
        i++;
    }

    motorsStop();
    Serial.println("[DRIVE] Ziel erreicht");
}

// ═════════════════════════════════════════════════════════════════
//  Servo (Core0)
// ═════════════════════════════════════════════════════════════════

static Servo g_servo;

static void servoSpin() {
    Serial.println("[SERVO] dreht");
    g_servo.attach(PIN_SERVO);
    while (true) {
        if (timeUp()) MOTORS_OFF();  // Sicherheitsnetz
        g_servo.write(90);
        delay(500);
        if (timeUp()) MOTORS_OFF();
        g_servo.write(0);
        delay(500);
    }
}

// ═════════════════════════════════════════════════════════════════
//  CORE 0 — Hauptablauf
// ═════════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    sleep_ms(500);

    const uint motor_pins[] = { L_STEP, L_DIR, L_EN, R_STEP, R_DIR, R_EN };
    for (uint p : motor_pins) { gpio_init(p); gpio_set_dir(p, GPIO_OUT); }
    gpio_put(L_EN, 1); gpio_put(R_EN, 1);  // EN aus beim Start

    Serial.println("[CORE0] bereit — warte auf Core1 ToF-Init...");
    sleep_ms(2500);

    waitForPullcord();
    delay(86000);
    driveForward(TARGET_MM);
    servoSpin();
}

void loop() {}

// ═════════════════════════════════════════════════════════════════
//  CORE 1 — ToF-Dauerschleife, setzt opponent_detected Flag
// ═════════════════════════════════════════════════════════════════

void setup1() {
    sleep_ms(500);

    i2c_init(I2C_PORT, 100000);
    gpio_set_function(PIN_SDA, GPIO_FUNC_I2C); gpio_pull_up(PIN_SDA);
    gpio_set_function(PIN_SCL, GPIO_FUNC_I2C); gpio_pull_up(PIN_SCL);
    gpio_init(PIN_XSHUT1); gpio_set_dir(PIN_XSHUT1, GPIO_OUT);
    gpio_init(PIN_XSHUT2); gpio_set_dir(PIN_XSHUT2, GPIO_OUT);

    tof_init_dual();
    Serial.println("[CORE1] ToF bereit");
}

void loop1() {
    mf_left.push(tof_read_raw(ADDR_LEFT));
    mf_right.push(tof_read_raw(ADDR_RIGHT));

    uint16_t l = mf_left.median();
    uint16_t r = mf_right.median();
    tof_left  = l;
    tof_right = r;

    bool obs = (l != 9999 && l < STOP_MM) || (r != 9999 && r < STOP_MM);

    if (obs != opponent_detected) {
        opponent_detected = obs;
        Serial.printf("[CORE1] opponent=%d  L=%d mm  R=%d mm\n",
                      (int)opponent_detected, l, r);
    } else {
        Serial.printf("[CORE1] L=%d mm  R=%d mm\n", l, r);
    }

    sleep_ms(20);
}