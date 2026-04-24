#include "pico/stdlib.h"
#include "hardware/pwm.h"
#include "servo.h"

#define SERVO_PIN 22

void servoInit() {
    gpio_set_function(SERVO_PIN, GPIO_FUNC_PWM);
    uint slice = pwm_gpio_to_slice_num(SERVO_PIN);
    // 50 Hz PWM: 125 MHz / 64 / 39063 ≈ 50 Hz
    pwm_set_clkdiv(slice, 64.0f);
    pwm_set_wrap(slice, 39062);
    pwm_set_enabled(slice, true);
}

void servoSpinForever() {
    while (true) {
        pwm_set_gpio_level(SERVO_PIN, 1953); // 1000 µs — eine Endlage
        sleep_ms(600);
        pwm_set_gpio_level(SERVO_PIN, 3906); // 2000 µs — andere Endlage
        sleep_ms(600);
    }
}