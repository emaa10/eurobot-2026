#include <Arduino.h>
#include "odometry.h"
// #include "pathfinder.h"

// Position start(1500, 500);
// Position target(500, 1500);

int pwm_left[2] = {0, 0};
int pwm_right[2] = {0, 0};

void setup() {
    Serial.begin(115200);
    Serial.setTimeout(5);

    pinMode(ENC_LEFT_A_PHASE, INPUT_PULLUP);
    pinMode(ENC_LEFT_B_PHASE, INPUT_PULLUP);
    pinMode(ENC_RIGHT_A_PHASE, INPUT_PULLUP);
    pinMode(ENC_RIGHT_B_PHASE, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(ENC_LEFT_A_PHASE), changeLeft, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ENC_RIGHT_A_PHASE), changeRight, CHANGE);

    // Pathfinder pathfinder(start, target);
    // pathfinder.plan();
}

void flush_serial(){
    while(Serial.available() > 0){
        String data = Serial.readStringUntil('\n');
    }
}

void getData(){
    if(Serial.available() <= 0){
        return;
    }

    String data = Serial.readStringUntil('\n');

    char charBuf[data.length() + 1];
    data.toCharArray(charBuf, sizeof(charBuf));

    char* token = strtok(charBuf, ";");
    
    // pwm values for left motor
    for (int i = 0; i < 2 && token != NULL; i++) {
        pwm_left[i] = atoi(token);
        token = strtok(NULL, ";");
    }
    
    // pwm values for right motor
    for (int i = 0; i < 2 && token != NULL; i++) {
        pwm_right[i] = atoi(token);
        token = strtok(NULL, ";");
    }

}

void loop() {
    updatePos();
    delay(5);
    getData();
}
