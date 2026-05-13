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

#define MOTORS_ON()  do { gpio_put(L_EN, 0); gpio_put(R_EN, 0); } while(0)
#define MOTORS_OFF() do { gpio_put(L_EN, 1); gpio_put(R_EN, 1); } while(0)

// ── Kalibrierung ──────────────────────────────────────────────────
static constexpr float STEPS_PER_MM   = 980.0f / 1000.0f;
static constexpr float DELAY_START_US = 6000.0f;
static constexpr float DELAY_MIN_US   = 2500.0f;
static constexpr float RAMP_US        = 150.0f;

// ── ToF ───────────────────────────────────────────────────────────
#define I2C_PORT      i2c1
#define PIN_SDA       2
#define PIN_SCL       3
#define ADDR_DEFAULT  0x29
#define ADDR_LEFT     0x30
#define ADDR_RIGHT    0x29
#define STOP_MM       80

// ── Fahrziel ──────────────────────────────────────────────────────
#define TARGET_MM     1500

// ═════════════════════════════════════════════════════════════════
//  Interrupt-Flag (Core1 schreibt, Core0 liest)
// ═════════════════════════════════════════════════════════════════
volatile bool opponent_detected = false;
volatile uint16_t tof_left      = 9999;
volatile uint16_t tof_right     = 9999;

// ═════════════════════════════════════════════════════════════════
//  ToF (läuft auf Core1)
// ═════════════════════════════════════════════════════════════════

// Median-Filter: nur echte Werte im Buffer, erst ab 3 Samples gültig
struct MedianFilter {
    static constexpr uint8_t N     = 7;   // größerer Buffer = robuster
    static constexpr uint8_t READY = 3;   // min. Samples bevor Ergebnis gültig
    uint16_t buf[N];
    uint8_t  idx   = 0;
    uint8_t  count = 0;

    MedianFilter() { for (auto &v : buf) v = 9999; }

    // Nur echte Messwerte pushen (kein 9999, keine Ausreißer unter 30mm oder über 2000mm)
    void push(uint16_t v) {
        if (v == 9999 || v > 2000) return;   // komplett ungültig — verwerfen
        if (v < 30)                return;   // Sensoreigenrauschen — verwerfen
        buf[idx] = v;
        idx = (idx + 1) % N;
        if (count < N) count++;
    }

    // Gibt 9999 zurück wenn noch zu wenige echte Samples vorhanden
    uint16_t median() const {
        if (count < READY) return 9999;
        uint16_t tmp[N];
        for (uint8_t i = 0; i < N; i++) tmp[i] = buf[i];
        for (uint8_t i = 0; i < N-1; i++)
            for (uint8_t j = 0; j < N-1-i; j++)
                if (tmp[j] > tmp[j+1]) { uint16_t t=tmp[j]; tmp[j]=tmp[j+1]; tmp[j+1]=t; }
        return tmp[count / 2];  // Median über tatsächlich gefüllte Slots
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
        if (stable == 0) { Serial.println("[PULLCORD] gezogen — los!"); return; }
        sleep_ms(150);
    }
}

// ═════════════════════════════════════════════════════════════════
//  Motor (Core0)
// ═════════════════════════════════════════════════════════════════

static inline void pulse() {
    gpio_put(L_STEP, 1); gpio_put(R_STEP, 1);
    sleep_us(30);
    gpio_put(L_STEP, 0); gpio_put(R_STEP, 0);
}

static void driveForward(uint32_t target_mm) {
    uint32_t total_steps = (uint32_t)(target_mm * STEPS_PER_MM);
    float    delay_us    = DELAY_START_US;
    uint32_t decel_start = total_steps > 80 ? total_steps - 80 : 0;

    gpio_put(L_DIR, 1);
    gpio_put(R_DIR, 0);
    MOTORS_ON();
    Serial.printf("[DRIVE] Start: %u mm → %u steps\n", target_mm, total_steps);

    for (uint32_t i = 0; i < total_steps; ) {

        // ── Interrupt-Flag prüfen ─────────────────────────────────
        if (opponent_detected) {
            MOTORS_OFF();
            Serial.printf("[CORE0] Gegner! L=%d R=%d mm — warte...\n", tof_left, tof_right);
            uint32_t waited = 0;
            while (opponent_detected) {
                sleep_ms(20);
                waited += 20;
                if (waited >= 10000) {
                    Serial.println("[CORE0] 10s Timeout — abgebrochen");
                    return;
                }
            }
            Serial.println("[CORE0] Weg frei — weiter");
            MOTORS_ON();
            continue;   // i nicht erhöhen
        }

        // ── Rampe ─────────────────────────────────────────────────
        if (i < total_steps / 2 && delay_us > DELAY_MIN_US)
            delay_us = fmaxf(delay_us - RAMP_US, DELAY_MIN_US);
        if (i >= decel_start && delay_us < DELAY_START_US)
            delay_us = fminf(delay_us + RAMP_US, DELAY_START_US);

        pulse();
        sleep_us((uint32_t)delay_us);

        if (i % 300 == 0)
            Serial.printf("[DRIVE] %u/%u  L=%d R=%d mm\n", i, total_steps, tof_left, tof_right);
        i++;
    }

    MOTORS_OFF();
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
        g_servo.write(90); delay(500);
        g_servo.write(0);  delay(500);
    }
}

// ═════════════════════════════════════════════════════════════════
//  CORE 0 — Hauptablauf
// ═════════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    sleep_ms(500);

    // Motor-GPIOs
    const uint motor_pins[] = { L_STEP, L_DIR, L_EN, R_STEP, R_DIR, R_EN };
    for (uint p : motor_pins) { gpio_init(p); gpio_set_dir(p, GPIO_OUT); }
    MOTORS_OFF();

    Serial.println("[CORE0] bereit — warte auf Core1 ToF-Init...");
    sleep_ms(2500);  // Core1 Zeit zum Initialisieren

    waitForPullcord();
    driveForward(TARGET_MM);
    servoSpin();
}

void loop() {}

// ═════════════════════════════════════════════════════════════════
//  CORE 1 — ToF-Dauerschleife, setzt opponent_detected Flag
// ═════════════════════════════════════════════════════════════════

void setup1() {
    sleep_ms(500);

    // I2C + XSHUT
    i2c_init(I2C_PORT, 100000);
    gpio_set_function(PIN_SDA, GPIO_FUNC_I2C); gpio_pull_up(PIN_SDA);
    gpio_set_function(PIN_SCL, GPIO_FUNC_I2C); gpio_pull_up(PIN_SCL);
    gpio_init(PIN_XSHUT1); gpio_set_dir(PIN_XSHUT1, GPIO_OUT);
    gpio_init(PIN_XSHUT2); gpio_set_dir(PIN_XSHUT2, GPIO_OUT);

    tof_init_dual();
    Serial.println("[CORE1] ToF bereit");
}

void loop1() {
    // push() filtert intern: ungültige Werte, <30mm, >2000mm werden verworfen
    mf_left.push(tof_read_raw(ADDR_LEFT));
    mf_right.push(tof_read_raw(ADDR_RIGHT));

    uint16_t l = mf_left.median();
    uint16_t r = mf_right.median();
    tof_left  = l;
    tof_right = r;

    // Gegner nur erkannt wenn Median gültig (>=3 echte Samples) UND unter Schwelle
    bool obs = (l != 9999 && l < STOP_MM) || (r != 9999 && r < STOP_MM);

    if (obs != opponent_detected) {
        opponent_detected = obs;
        Serial.printf("[CORE1] opponent=%d  L=%d mm  R=%d mm\n",
                      (int)opponent_detected, l, r);
    } else {
        Serial.printf("[CORE1] L=%d mm  R=%d mm\n", l, r);
    }

    sleep_ms(20);  // 50 Hz
}