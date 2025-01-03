#include <Arduino.h>
#include "odometry.h"

// left dc motor pins
#define LEFT_LPWM 10 //44
#define LEFT_RPWM 11 //45

// right dc motor pins
#define RIGHT_LPWM 9//41
#define RIGHT_RPWM 8//40


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

void write_pwm(int pwm_left[2], int pwm_right[2]){
    analogWrite(LEFT_LPWM, pwm_left[0]);
    analogWrite(LEFT_RPWM, pwm_left[1]);
    analogWrite(RIGHT_LPWM, pwm_right[0]);
    analogWrite(RIGHT_RPWM, pwm_right[1]);
}

void getData(){
    int pwm_left[2] = {0, 0};
    int pwm_right[2] = {0, 0};

    if(Serial.available() <= 0){
        return;
    }

    String data = Serial.readStringUntil('\n');

    if(data[0] == 'r'){
        counterLeft = 0;
        counterRight = 0;
        lastCounterLeft = 0;
        lastCounterRight = 0;

        return;
    }

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

    write_pwm(pwm_left, pwm_right);
}

void loop() {
    send_counter();
    getData();
}
