#pragma once
#include <stdint.h>

// Wird von Core0 geschrieben, von Core1 gelesen.
// volatile reicht für RP2040 bei primitiven Typen.
extern volatile bool     opponent_detected;
extern volatile uint16_t last_dist_l;
extern volatile uint16_t last_dist_r;
