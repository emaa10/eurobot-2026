#include <Servo.h>
#include <Arduino.h>

#define SERVO_PIN 28

Servo servo1;

void setup() {
    Serial.begin(115200);
    sleep_ms(500);

    servo1.attach(SERVO_PIN);
    servo1.write(90);  // stop
    Serial.println("Servo bereit");
    sleep_ms(1000);

    while (true) {
        servo1.write(0);
        delay(1000);
        servo1.write(90);
        delay(1000);
        servo1.write(180);
        delay(1000);
        servo1.write(90);
        delay(1000);
    }
}

void loop() {}
