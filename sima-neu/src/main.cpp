// ── ToF-Test mit XSHUT-Adressvergabe + Median-Filter ─────────────
// Beide VL53L0X hängen auf i2c1 (SDA=GP2, SCL=GP3).
// XSHUT1 = GP20 (linker Sensor)
// XSHUT2 = GP19 (rechter Sensor)

#include <Arduino.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"

// ── I2C ──────────────────────────────────────────────────────────
#define I2C_PORT   i2c1
#define PIN_SDA    2
#define PIN_SCL    3

// ── XSHUT ────────────────────────────────────────────────────────
#define PIN_XSHUT1  20
#define PIN_XSHUT2  19

// ── Adressen ─────────────────────────────────────────────────────
#define ADDR_DEFAULT  0x29
#define ADDR_LEFT     0x30
#define ADDR_RIGHT    0x29

// ── Plausibilitätsgrenzen ─────────────────────────────────────────

#define TOF_MAX_MM  2000    // VL53L0X Maxreichweite

// ── Median-Filter (5 Samples) ─────────────────────────────────────
struct MedianFilter {
    static constexpr uint8_t N = 5;
    uint16_t buf[N];
    uint8_t  idx   = 0;
    uint8_t  count = 0;

    MedianFilter() { for (auto &v : buf) v = 9999; }

    void push(uint16_t v) {
        buf[idx] = v;
        idx = (idx + 1) % N;
        if (count < N) count++;
    }

    uint16_t median() const {
        uint16_t tmp[N];
        for (uint8_t i = 0; i < N; i++) tmp[i] = buf[i];
        // Bubblesort über N Elemente (N=5, kein Problem)
        for (uint8_t i = 0; i < N - 1; i++)
            for (uint8_t j = 0; j < N - 1 - i; j++)
                if (tmp[j] > tmp[j+1]) { uint16_t t = tmp[j]; tmp[j] = tmp[j+1]; tmp[j+1] = t; }
        return tmp[N / 2];
    }
};

static MedianFilter mf_left, mf_right;

// ── VL53L0X Primitiven ────────────────────────────────────────────
static void tof_write(uint8_t addr, uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    i2c_write_blocking(I2C_PORT, addr, buf, 2, false);
}

static bool tof_ping(uint8_t addr) {
    uint8_t reg = 0x00;
    return i2c_write_blocking(I2C_PORT, addr, &reg, 1, false) >= 0;
}

static void tof_set_address(uint8_t new_addr) {
    tof_write(ADDR_DEFAULT, 0x8A, new_addr & 0x7F);
}

static void tof_start(uint8_t addr) {
    tof_write(addr, 0x80, 0x01); tof_write(addr, 0xFF, 0x01);
    tof_write(addr, 0x00, 0x00); tof_write(addr, 0x91, 0x3C);
    tof_write(addr, 0x00, 0x01); tof_write(addr, 0xFF, 0x00);
    tof_write(addr, 0x80, 0x00); tof_write(addr, 0x00, 0x02);
}

// Rohwert lesen — gibt 9999 bei I2C-Fehler oder bekannten Fehlwerten
static uint16_t tof_read_raw(uint8_t addr) {
    uint8_t reg = 0x1E, buf[2] = {0, 0};
    if (i2c_write_blocking(I2C_PORT, addr, &reg, 1, true) < 0) return 9999;
    i2c_read_blocking(I2C_PORT, addr, buf, 2, false);
    uint16_t v = (buf[0] << 8) | buf[1];
    if (v == 0 || v == 20 || v == 8190 || v == 9999) return 9999;
    return v;
}

// Plausibel + gefiltert
static uint16_t tof_read_filtered(uint8_t addr, MedianFilter &mf) {
    uint16_t raw = tof_read_raw(addr);

    // Plausibilitätscheck vor dem Filter
    if (raw != 9999 && raw <= TOF_MAX_MM)
        mf.push(raw);
    // bei 9999 nichts pushen — alter Pufferwert bleibt

    uint16_t med = mf.median();
    // Wenn der Median selbst noch 9999 ist (Buffer leer / alle invalid)
    return med;
}

// ── XSHUT-Init ────────────────────────────────────────────────────
static void tof_init_dual() {
    gpio_put(PIN_XSHUT1, 0);
    gpio_put(PIN_XSHUT2, 0);
    sleep_ms(10);

    gpio_put(PIN_XSHUT1, 1);
    sleep_ms(10);
    tof_set_address(ADDR_LEFT);
    sleep_ms(5);
    Serial.printf("[INIT] Links  0x%02X  Ping: %s\n",
                  ADDR_LEFT, tof_ping(ADDR_LEFT) ? "OK" : "FEHLER");
    tof_start(ADDR_LEFT);

    gpio_put(PIN_XSHUT2, 1);
    sleep_ms(10);
    Serial.printf("[INIT] Rechts 0x%02X  Ping: %s\n",
                  ADDR_RIGHT, tof_ping(ADDR_RIGHT) ? "OK" : "FEHLER");
    tof_start(ADDR_RIGHT);
}

// ── Setup ─────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    sleep_ms(500);

    i2c_init(I2C_PORT, 100000);
    gpio_set_function(PIN_SDA, GPIO_FUNC_I2C); gpio_pull_up(PIN_SDA);
    gpio_set_function(PIN_SCL, GPIO_FUNC_I2C); gpio_pull_up(PIN_SCL);

    gpio_init(PIN_XSHUT1); gpio_set_dir(PIN_XSHUT1, GPIO_OUT);
    gpio_init(PIN_XSHUT2); gpio_set_dir(PIN_XSHUT2, GPIO_OUT);

    tof_init_dual();
    Serial.println("[TOF] Bereit");
}

// ── Loop ──────────────────────────────────────────────────────────
void loop() {
    uint16_t l = tof_read_filtered(ADDR_LEFT,  mf_left);
    uint16_t r = tof_read_filtered(ADDR_RIGHT, mf_right);

    if (l == 9999)
        Serial.printf("[TOF] L= --- mm  R=%4d mm\n", r);
    else if (r == 9999)
        Serial.printf("[TOF] L=%4d mm  R= --- mm\n", l);
    else
        Serial.printf("[TOF] L=%4d mm  R=%4d mm\n", l, r);

    sleep_ms(50);
}