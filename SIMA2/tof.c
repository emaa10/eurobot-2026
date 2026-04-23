#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "hardware/timer.h"
#include "tof.h"
#define VL53_ADDR 0x29

void vl53_write(i2c_inst_t *i2c, uint8_t reg, uint8_t val) {    //Register schreiben
    uint8_t buf[2] = {reg, val};
    i2c_write_blocking(i2c, VL53_ADDR, buf, 2, false);
}

uint16_t vl53_read_distance(i2c_inst_t *i2c) {  //Distanz auslesen
    uint8_t reg = 0x1E;
    uint8_t buf[2];

    i2c_write_blocking(i2c, VL53_ADDR, &reg, 1, true);
    i2c_read_blocking(i2c, VL53_ADDR, buf, 2, false);

    return (buf[0] << 8) | buf[1];
}

void vl53_start_continuous(i2c_inst_t *i2c) {   //Continuous Mode starten
    vl53_write(i2c, 0x80, 0x01);
    vl53_write(i2c, 0xFF, 0x01);
    vl53_write(i2c, 0x00, 0x00);
    vl53_write(i2c, 0x91, 0x3C);
    vl53_write(i2c, 0x00, 0x01);
    vl53_write(i2c, 0xFF, 0x00);
    vl53_write(i2c, 0x80, 0x00);
    vl53_write(i2c, 0x00, 0x02);
}

void vl53Init(void)
{
    i2c_init(i2c1, 100000);                 //Initialisierung I^2C Schnittstellen
    gpio_set_function(2, GPIO_FUNC_I2C);
    gpio_set_function(3, GPIO_FUNC_I2C);
    gpio_pull_up(2);
    gpio_pull_up(3);

    i2c_init(i2c0, 100000);                
    gpio_set_function(12, GPIO_FUNC_I2C);
    gpio_set_function(13, GPIO_FUNC_I2C);
    gpio_pull_up(12);
    gpio_pull_up(13);

    vl53_start_continuous(i2c1);
    vl53_start_continuous(i2c0);
}
