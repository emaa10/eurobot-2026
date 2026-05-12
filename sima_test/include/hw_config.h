#pragma once
#include <stdint.h>

// ── Pins ──────────────────────────────────────────────────
static constexpr uint PIN_PULLCORD = 21;
static constexpr uint PIN_SERVO    = 28;
static constexpr uint PIN_LED      = 25;

// ── Stepper ───────────────────────────────────────────────
static constexpr uint L_STEP = 0;
static constexpr uint L_DIR  = 1;
static constexpr uint L_EN   = 7;
static constexpr uint R_STEP = 10;
static constexpr uint R_DIR  = 9;
static constexpr uint R_EN   = 15;

// ── Kalibrierung ──────────────────────────────────────────
static constexpr float STEPS_PER_MM  = 980.0f / 1000.0f;
static constexpr float STEPS_PER_DEG = 200.0f / 90.0f;
static constexpr float DELAY_START_US = 6000.0f;
static constexpr float DELAY_MIN_US   = 2500.0f;
static constexpr float RAMP_US        = 150.0f;

// ── ToF ───────────────────────────────────────────────────
static constexpr uint8_t  VL53_ADDR = 0x29;
static constexpr uint16_t STOP_MM   = 400;

// ── Makros ────────────────────────────────────────────────
#define MOTORS_ON()  do { gpio_put(L_EN, 0); gpio_put(R_EN, 0); } while(0)
#define MOTORS_OFF() do { gpio_put(L_EN, 1); gpio_put(R_EN, 1); } while(0)
