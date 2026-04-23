#ifndef TOF_H
#define TOF_H

#include <stdint.h>
#include <stdbool.h>
#include "hardware/i2c.h"

void vl53_write(i2c_inst_t *i2c, uint8_t reg, uint8_t val);
uint16_t vl53_read_distance(i2c_inst_t *i2c);
void vl53_start_continuous(i2c_inst_t *i2c);
void vl53Init(void);

#endif
