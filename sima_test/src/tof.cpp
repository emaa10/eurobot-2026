#include "tof.h"
#include "hw_config.h"

MedianFilter filter_l;
MedianFilter filter_r;

bool tof_valid(uint16_t v) {
    return v != 0 && v != 20 && v != 8190 && v != 9999;
}

bool tof_ping(i2c_inst_t *i2c) {
    uint8_t reg = 0x00;
    return i2c_write_blocking(i2c, VL53_ADDR, &reg, 1, false) >= 0;
}

void tof_write(i2c_inst_t *i2c, uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    i2c_write_blocking(i2c, VL53_ADDR, buf, 2, false);
}

uint16_t tof_read_raw(i2c_inst_t *i2c) {
    uint8_t reg = 0x1E;
    uint8_t buf[2] = {0xFF, 0xFF};
    if (i2c_write_blocking(i2c, VL53_ADDR, &reg, 1, true) < 0) return 9999;
    i2c_read_blocking(i2c, VL53_ADDR, buf, 2, false);
    return (static_cast<uint16_t>(buf[0]) << 8) | buf[1];
}

void tof_start(i2c_inst_t *i2c) {
    tof_write(i2c, 0x80, 0x01);
    tof_write(i2c, 0xFF, 0x01);
    tof_write(i2c, 0x00, 0x00);
    tof_write(i2c, 0x91, 0x3C);
    tof_write(i2c, 0x00, 0x01);
    tof_write(i2c, 0xFF, 0x00);
    tof_write(i2c, 0x80, 0x00);
    tof_write(i2c, 0x00, 0x02);
}
