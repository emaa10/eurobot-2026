#include <Arduino.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"

#define VL53_ADDR 0x29

static void tof_write(i2c_inst_t *i2c, uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    i2c_write_blocking(i2c, VL53_ADDR, buf, 2, false);
}

static uint16_t tof_read_raw(i2c_inst_t *i2c) {
    uint8_t reg = 0x1E;
    uint8_t buf[2] = {0xFF, 0xFF};
    if (i2c_write_blocking(i2c, VL53_ADDR, &reg, 1, true) < 0) return 9999;
    i2c_read_blocking(i2c, VL53_ADDR, buf, 2, false);
    return (uint16_t)((buf[0] << 8) | buf[1]);
}

static void tof_start(i2c_inst_t *i2c) {
    tof_write(i2c, 0x80, 0x01); tof_write(i2c, 0xFF, 0x01); tof_write(i2c, 0x00, 0x00);
    tof_write(i2c, 0x91, 0x3C); tof_write(i2c, 0x00, 0x01); tof_write(i2c, 0xFF, 0x00);
    tof_write(i2c, 0x80, 0x00); tof_write(i2c, 0x00, 0x02);
}

void setup() {
    Serial.begin(115200);
    Serial.println("Starte Servo-Test...");
    sleep_ms(500);

    i2c_init(i2c1, 100000);
    gpio_set_function(2, GPIO_FUNC_I2C); gpio_pull_up(2);
    gpio_set_function(3, GPIO_FUNC_I2C); gpio_pull_up(3);

    i2c_init(i2c0, 100000);
    gpio_set_function(12, GPIO_FUNC_I2C); gpio_pull_up(12);
    gpio_set_function(13, GPIO_FUNC_I2C); gpio_pull_up(13);

    tof_start(i2c1);
    tof_start(i2c0);

    Serial.println("ToF bereit");
}

void loop() {
    uint16_t l = tof_read_raw(i2c1);
    uint16_t r = tof_read_raw(i2c0);
    Serial.printf("[TOF] L=%u R=%u\n", l, r);
    delay(200);
}
