#include "pico/stdlib.h"
#include "hardware/pwm.h"
#include "servo.h"

static int counter = 0; 
static int timer = 10;

void servoInit()
{
    #define ServoPin 22  //Initialisierung Servo

    gpio_set_function(ServoPin, GPIO_FUNC_PWM);     
    uint slice = pwm_gpio_to_slice_num(ServoPin);

    //50 Hz PWM: 20 ms Periode 
    pwm_set_clkdiv(slice, 64.0f);
    pwm_set_wrap(slice, 39062); // 125 MHz / 64 = 1.953 MHz

    pwm_set_enabled(slice, true);
}

void setServoCounter()
{
    counter = counter ++;
}

void servoTurn()
{
    if(counter != 15)
    {
        return;
    }
    if(counter == 15)
    {
        while(true)
        {
            pwm_set_gpio_level(ServoPin, 2929); // 1500 µs
            sleep_ms(500);

            pwm_set_gpio_level(ServoPin, 3906); // 2000 µs
            sleep_ms(500);

            pwm_set_gpio_level(ServoPin, 1953); // 1000 µs
            sleep_ms(500);
        }
    }

}