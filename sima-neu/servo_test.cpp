#include <Arduino.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"

#define I2C_PORT     i2c1
#define PIN_SDA      2
#define PIN_SCL      3
#define PIN_XSHUT1   20
#define PIN_XSHUT2   19
#define ADDR_DEFAULT 0x29
#define ADDR_LEFT    0x30
#define ADDR_RIGHT   0x29

static void tof_write(uint8_t addr, uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    i2c_write_blocking(I2C_PORT, addr, buf, 2, false);
}

static void tof_start(uint8_t addr) {
    tof_write(addr, 0x80, 0x01); tof_write(addr, 0xFF, 0x01);
    tof_write(addr, 0x00, 0x00); tof_write(addr, 0x91, 0x3C);
    tof_write(addr, 0x00, 0x01); tof_write(addr, 0xFF, 0x00);
    tof_write(addr, 0x80, 0x00); tof_write(addr, 0x00, 0x02);
}

static uint16_t tof_read(uint8_t addr) {
    uint8_t reg = 0x1E, buf[2] = {0, 0};
    if (i2c_write_blocking(I2C_PORT, addr, &reg, 1, true) < 0) return 9999;
    i2c_read_blocking(I2C_PORT, addr, buf, 2, false);
    uint16_t v = (buf[0] << 8) | buf[1];
    if (v == 0 || v == 20 || v == 8190 || v == 9999) return 9999;
    return v;
}

void setup() {
    Serial.begin(115200);
    Serial.println("Sensor start");
    sleep_ms(500);
    delay(5000);
    Serial.println("Sensor starte");

    i2c_init(I2C_PORT, 100000);
    gpio_set_function(PIN_SDA, GPIO_FUNC_I2C); gpio_pull_up(PIN_SDA);
    gpio_set_function(PIN_SCL, GPIO_FUNC_I2C); gpio_pull_up(PIN_SCL);
    Serial.println("before init");
    gpio_init(PIN_XSHUT1); gpio_set_dir(PIN_XSHUT1, GPIO_OUT);
    gpio_init(PIN_XSHUT2); gpio_set_dir(PIN_XSHUT2, GPIO_OUT);
    Serial.println("after init");
    // Sensor 1 (Links) auf neue Adresse setzen
    gpio_put(PIN_XSHUT1, 0); gpio_put(PIN_XSHUT2, 0);
    sleep_ms(10);
    gpio_put(PIN_XSHUT1, 1); sleep_ms(10);
    tof_write(ADDR_DEFAULT, 0x8A, ADDR_LEFT & 0x7F);
    sleep_ms(5);
    tof_start(ADDR_LEFT);

    // Sensor 2 (Rechts) auf Default-Adresse lassen
    gpio_put(PIN_XSHUT2, 1); sleep_ms(10);
    tof_start(ADDR_RIGHT);

    Serial.println("Links (mm) | Rechts (mm)");
}

void loop() {
    uint16_t l = tof_read(ADDR_LEFT);
    uint16_t r = tof_read(ADDR_RIGHT);
    Serial.printf("L: %4d mm  |  R: %4d mm\n", l, r);
    delay(100);
}