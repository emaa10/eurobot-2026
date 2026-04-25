#include <Arduino.h>
#include <Servo.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include <math.h>

// ── Pins ──────────────────────────────────────────────────────
#define PIN_PULLCORD  21
#define SERVO_PIN     22
#define PIN_LED       25

// ── Motor-Pins ────────────────────────────────────────────────
#define L_STEP  0
#define L_DIR   1
#define L_EN    7
#define R_STEP  10
#define R_DIR   9
#define R_EN    15

#define MOTORS_ON()   do { gpio_put(L_EN, 0); gpio_put(R_EN, 0); } while(0)
#define MOTORS_OFF()  do { gpio_put(L_EN, 1); gpio_put(R_EN, 1); } while(0)

// ── Kalibrierung ──────────────────────────────────────────────
static constexpr float STEPS_PER_MM  = 980.0f / 1000.0f;
static constexpr float STEPS_PER_DEG = 200.0f / 90.0f;

static constexpr float DELAY_START_US = 6000.0f;
static constexpr float DELAY_MIN_US   = 2500.0f;
static constexpr float RAMP_US        = 150.0f;

// ── ToF ───────────────────────────────────────────────────────
#define VL53_ADDR   0x29
#define STOP_MM     500
#define RESUME_MM   540
#define BELOW_LIMIT 5

volatile bool opponent_detected = false;
volatile uint16_t last_dist_l = 9999;
volatile uint16_t last_dist_r = 9999;
static uint32_t tactic_start_ms = 0;
#define TACTIC_TIMEOUT_MS 99000

static bool tof_valid(uint16_t v) {
    return v != 0 && v != 20 && v != 8190 && v != 9999;
}

struct MedianFilter {
    uint16_t buf[3] = {9999, 9999, 9999};
    uint8_t  idx = 0;

    void push(uint16_t v) {
        if (!tof_valid(v)) return;
        buf[idx] = v;
        idx = (idx + 1) % 3;
    }

    uint16_t median() const {
        uint16_t a = buf[0], b = buf[1], c = buf[2];
        if (a > b) { uint16_t t = a; a = b; b = t; }
        if (b > c) { uint16_t t = b; b = c; c = t; }
        if (a > b) { uint16_t t = a; a = b; b = t; }
        return b;
    }
};

static MedianFilter filter_l, filter_r;

static void tof_write(i2c_inst_t *i2c, uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    i2c_write_blocking(i2c, VL53_ADDR, buf, 2, false);
}

static uint16_t tof_read_raw(i2c_inst_t *i2c) {
    uint8_t reg = 0x1E, buf[2] = {0xFF, 0xFF};
    if (i2c_write_blocking(i2c, VL53_ADDR, &reg, 1, true) < 0) return 9999;
    i2c_read_blocking(i2c, VL53_ADDR, buf, 2, false);
    return (buf[0] << 8) | buf[1];
}

static void tof_start(i2c_inst_t *i2c) {
    tof_write(i2c, 0x80, 0x01); tof_write(i2c, 0xFF, 0x01); tof_write(i2c, 0x00, 0x00);
    tof_write(i2c, 0x91, 0x3C); tof_write(i2c, 0x00, 0x01); tof_write(i2c, 0xFF, 0x00);
    tof_write(i2c, 0x80, 0x00); tof_write(i2c, 0x00, 0x02);
}

// ── Core 0: ToF-Loop ─────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    sleep_ms(500);

    i2c_init(i2c1, 100000);
    gpio_set_function(2, GPIO_FUNC_I2C); gpio_pull_up(2);
    gpio_set_function(3, GPIO_FUNC_I2C); gpio_pull_up(3);

    i2c_init(i2c0, 100000);
    gpio_set_function(12, GPIO_FUNC_I2C); gpio_pull_up(12);
    gpio_set_function(13, GPIO_FUNC_I2C); gpio_pull_up(13);

    tof_start(i2c1);
    tof_start(i2c0);

    Serial.println("Core0: ToF bereit");
}

void loop() {
    static int below = 0;

    filter_l.push(tof_read_raw(i2c1));
    filter_r.push(tof_read_raw(i2c0));

    uint16_t d1 = filter_l.median();
    uint16_t d2 = filter_r.median();
    last_dist_l = d1;
    last_dist_r = d2;

    bool obstacle = tof_valid(d1) && tof_valid(d2) && (d1 < STOP_MM || d2 < STOP_MM);

    if (obstacle) { below++; } else if (below > 0) { below--; }

    if (!opponent_detected && below >= BELOW_LIMIT) {
        opponent_detected = true;
        Serial.printf("[STOPP] L=%dmm R=%dmm\n", d1, d2);
    }
    if (opponent_detected && tof_valid(d1) && tof_valid(d2) && d1 > RESUME_MM && d2 > RESUME_MM) {
        opponent_detected = false;
        below = 0;
        Serial.printf("[FREI]  L=%dmm R=%dmm\n", d1, d2);
    }

    sleep_ms(20);  // 50 Hz
}

// ── Internes Step-Handling ────────────────────────────────────

static inline void pulse(uint pin) {
    gpio_put(pin, 1);
    sleep_us(30);
    gpio_put(pin, 0);
}

static void run_steps(uint32_t steps, bool check_opponent) {
    Serial.printf("[motor] start: %u steps, opponent_check=%d, opponent_detected=%d\n", steps, check_opponent, opponent_detected);
    float delay_us = DELAY_START_US;
    uint32_t decel_start = steps > 80 ? steps - 80 : 0;

    for (uint32_t i = 0; i < steps; i++) {
        if (tactic_start_ms > 0 && (millis() - tactic_start_ms) >= TACTIC_TIMEOUT_MS) {
            MOTORS_OFF();
            Serial.println("[motor] 99s Timeout — Stepper gestoppt");
            return;
        }
        if (check_opponent && opponent_detected) {
            Serial.printf("[motor] PAUSE bei step %u — warte auf Freigabe\n", i);
            MOTORS_OFF();
            uint32_t blocked_ms = 0;
            while (opponent_detected) {
                sleep_ms(10);
                blocked_ms += 10;
                if (blocked_ms >= 10000) {
                    Serial.println("[motor] 10s Gegner — Fahrt abgebrochen");
                    return;
                }
            }
            Serial.println("[motor] RESUME");
            MOTORS_ON();
        }
        if (i < steps / 2 && delay_us > DELAY_MIN_US)
            delay_us = fmaxf(delay_us - RAMP_US, DELAY_MIN_US);
        if (i >= decel_start && delay_us < DELAY_START_US)
            delay_us = fminf(delay_us + RAMP_US, DELAY_START_US);

        pulse(L_STEP);
        pulse(R_STEP);
        sleep_us((uint32_t)delay_us);
    }
}

// ── Servo ─────────────────────────────────────────────────────
static Servo servo;

// ── Öffentliche API ───────────────────────────────────────────

// cm > 0 = vorwärts, cm < 0 = rückwärts
void drive(int cm) {
    if (cm == 0) return;
    uint32_t steps = (uint32_t)(fabsf((float)cm) * 10.0f * STEPS_PER_MM);
    Serial.printf("[drive] %dcm → %u steps, opponent_detected=%d\n", cm, steps, opponent_detected);

    gpio_put(L_DIR, cm > 0 ? 1 : 0);
    gpio_put(R_DIR, cm > 0 ? 0 : 1);

    MOTORS_ON();
    run_steps(steps, cm > 0);
    MOTORS_OFF();
    Serial.printf("[drive] fertig\n");
}

// angle > 0 = rechts, angle < 0 = links
void turn(int angle) {
    if (angle == 0) return;
    uint32_t steps = (uint32_t)(fabsf((float)angle) * STEPS_PER_DEG);

    gpio_put(L_DIR, angle > 0 ? 1 : 0);
    gpio_put(R_DIR, angle > 0 ? 1 : 0);

    MOTORS_ON();
    run_steps(steps, false);  // beim Drehen kein Gegner-Check
    MOTORS_OFF();

    Serial.printf("[turn]  %d° (%u steps)\n", angle, steps);
}

// ── Taktik-Methoden ───────────────────────────────────────────

void waitForPullcord() {
    gpio_init(PIN_PULLCORD);
    gpio_set_dir(PIN_PULLCORD, GPIO_IN);
    gpio_pull_down(PIN_PULLCORD);

    gpio_init(PIN_LED);
    gpio_set_dir(PIN_LED, GPIO_OUT);
    gpio_put(PIN_LED, 1);  // LED an: warte auf Zugschnur

    Serial.println("[PULLCORD] warte auf LOW...");
    int low_count = 0;
    while (true) {
        int state = gpio_get(PIN_PULLCORD);
        Serial.printf("[PULLCORD] GP%d = %d (%s)\n", PIN_PULLCORD, state, state ? "HIGH / offen" : "LOW / verbunden");
        if (state == 0) low_count++;
        else            low_count = 0;
        if (low_count >= 5) break;
        sleep_ms(200);
    }

    gpio_put(PIN_LED, 0);  // LED aus: Zugschnur gezogen
    Serial.println("[PULLCORD] gezogen, starte Taktik");
}

void waitForGegnerWeg() {
    Serial.println("[GEGNER] warte bis Weg frei...");
    gpio_init(14);
    gpio_set_dir(14, GPIO_OUT);
    gpio_put(14, 0);
    while (opponent_detected) {
        Serial.printf("[GEGNER] L=%dmm R=%dmm\n", last_dist_l, last_dist_r);
        sleep_ms(200);
    }
    gpio_put(14, 1);
    tactic_start_ms = millis();
    Serial.println("[GEGNER] Weg frei — Timer gestartet");
}

void servoSpin() {
    servo.attach(SERVO_PIN);
    servo.writeMicroseconds(1500);  // neutral / stop
    sleep_ms(200);
    servo.writeMicroseconds(2000);  // full speed
    Serial.println("[SERVO] dreht");
}

void runTactic() {
    waitForGegnerWeg();  // warte bis Weg frei, dann erst losfahren
    sleep_ms(86000);     // 85 Sekunden warten
    drive(100);          // 100 cm vorwärts
    servoSpin();
    while (true) sleep_ms(1000);
}

// ── Core 1 ────────────────────────────────────────────────────

void setup1() {
    gpio_init(L_STEP); gpio_set_dir(L_STEP, GPIO_OUT);
    gpio_init(L_DIR);  gpio_set_dir(L_DIR,  GPIO_OUT);
    gpio_init(L_EN);   gpio_set_dir(L_EN,   GPIO_OUT);
    gpio_init(R_STEP); gpio_set_dir(R_STEP, GPIO_OUT);
    gpio_init(R_DIR);  gpio_set_dir(R_DIR,  GPIO_OUT);
    gpio_init(R_EN);   gpio_set_dir(R_EN,   GPIO_OUT);
    MOTORS_OFF();

    sleep_ms(2000);  // warten bis Core0 ToF initialisiert hat
    Serial.println("Core1: bereit");

    //waitForPullcord();
}

void loop1() {
    runTactic();
}
