#include <Arduino.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"

#define I2C_PORT  i2c1
#define PIN_SDA   2
#define PIN_SCL   3
#define ADDR      0x29

static void tof_write(uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    i2c_write_blocking(I2C_PORT, ADDR, buf, 2, false);
}

static uint16_t tof_read() {
    uint8_t reg = 0x1E, buf[2] = {0, 0};
    if (i2c_write_blocking(I2C_PORT, ADDR, &reg, 1, true) < 0) {
        Serial.println("[TOF] I2C write FEHLER");
        return 9999;
    }
    i2c_read_blocking(I2C_PORT, ADDR, buf, 2, false);
    uint16_t raw = (buf[0] << 8) | buf[1];
    Serial.printf("[TOF] raw=0x%04X (%d)\n", raw, raw);
    if (raw == 0 || raw == 20 || raw == 8190 || raw == 9999) {
        Serial.println("[TOF] ungültiger Wert — verworfen");
        return 9999;
    }
    return raw;
}

void setup() {
    Serial.begin(115200);
    Serial.println("tets");
    sleep_ms(500);

    i2c_init(I2C_PORT, 100000);
    gpio_set_function(PIN_SDA, GPIO_FUNC_I2C); gpio_pull_up(PIN_SDA);
    gpio_set_function(PIN_SCL, GPIO_FUNC_I2C); gpio_pull_up(PIN_SCL);

    // Sensor starten
    tof_write(0x80, 0x01); tof_write(0xFF, 0x01);
    tof_write(0x00, 0x00); tof_write(0x91, 0x3C);
    tof_write(0x00, 0x01); tof_write(0xFF, 0x00);
    tof_write(0x80, 0x00); tof_write(0x00, 0x02);

    Serial.println("TOF links bereit");
}

void loop() {
    uint16_t v = tof_read();
    Serial.printf("L: %4d mm  [%s]\n", v, v == 9999 ? "UNGÜLTIG" : "OK");
    delay(100);
}