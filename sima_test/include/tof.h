#pragma once
#include <stdint.h>
#include "hardware/i2c.h"
#include "hw_config.h"

// ── Median-Filter (3 Samples) ─────────────────────────────
struct MedianFilter {
    uint16_t buf[3] = {9999, 9999, 9999};
    uint8_t  idx    = 0;

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

    static bool tof_valid(uint16_t v) {
        return v != 0 && v != 20 && v != 8190 && v != 9999;
    }
};

// ── Globale Filter-Instanzen ──────────────────────────────
extern MedianFilter filter_l;
extern MedianFilter filter_r;

// ── Freie Funktionen ──────────────────────────────────────
bool     tof_valid(uint16_t v);
bool     tof_ping (i2c_inst_t *i2c);
void     tof_write(i2c_inst_t *i2c, uint8_t reg, uint8_t val);
uint16_t tof_read_raw(i2c_inst_t *i2c);
void     tof_start(i2c_inst_t *i2c);
