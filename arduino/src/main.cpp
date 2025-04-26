#include <Arduino.h>
#include <math.h>

unsigned long lastPosUpdate = millis();

#define ENC_LEFT_A_PHASE 2
#define ENC_LEFT_B_PHASE 3
#define ENC_RIGHT_A_PHASE 18
#define ENC_RIGHT_B_PHASE 19

#define WHEELBASE_ENC 128
#define WHEELBASE_DRIVE 207
#define PULSES_PER_REV 1200
#define ENC_WHEEL_DIAMETER 50                                                                           
#define MOTOR_WHEEL_DIAMETER 70

const float encWheelScope = ENC_WHEEL_DIAMETER * M_PI;
const float pulsesPerMM = PULSES_PER_REV / encWheelScope;

int counterLeft = 0;
int counterRight = 0;

int lastCounterLeft = 0;
int lastCounterRight = 0;

float x = 0;            // x in mm
float y = 0;            // y in mm
float theta = 0;        // theta in RAD

// update ticks left
void changeLeft(){
    if(digitalRead(ENC_LEFT_B_PHASE) != digitalRead(ENC_LEFT_A_PHASE)){
        counterLeft++;
    } else {
        counterLeft --;
    }
}

// update ticks right
void changeRight(){
    if(digitalRead(ENC_RIGHT_B_PHASE) != digitalRead(ENC_RIGHT_A_PHASE)){
        counterRight++;
    } else {
        counterRight --;
    }
}

void send_pos(){
    String data;
    data += "p";
    data += String(int(x));
    data += ";";
    data += String(int(y));
    data += ";";
    data += String(theta * 180.0 / PI);
    Serial.println(data);
}

void updatePos(){
    // get tick differnce for each wheel
    float leftWheelDif = counterLeft - lastCounterLeft;
    float rightWheelDif = counterRight - lastCounterRight;

    // update last pos
    lastCounterLeft = counterLeft;
    lastCounterRight = counterRight;

    // distance per wheel
    float distanceLeft = leftWheelDif / pulsesPerMM;
    float distanceRight = rightWheelDif / pulsesPerMM;
    float distance = (distanceLeft + distanceRight) / 2;    //distance center has travelled

    // global position change
    float dtheta = (distanceLeft - distanceRight) / WHEELBASE_ENC;
    float dx = distance * cos(theta + dtheta);
    float dy = distance * sin(theta + dtheta);

    // update global pos
    x = x - dx;
    y = y - dy;
    theta = theta + dtheta;
    while (theta > 2 * M_PI) theta -= 2 * M_PI;
    while (theta < 0) theta += 2 * M_PI;

    send_pos();
}

void getData(){
    if(Serial.available() <= 0){
        return;
    }

    String data = Serial.readStringUntil('\n');

    if(data[0] == 'r'){
        counterLeft = 0;
        counterRight = 0;
        lastCounterLeft = 0;
        lastCounterRight = 0;
    }

    if(data[0] == 's'){
        int x_pos = 0;
        int y_pos = 0;
        int theta_pos = 0;
        
        // Find positions of semicolons
        int first_semicolon = data.indexOf(';');
        int second_semicolon = data.indexOf(';', first_semicolon + 1);
        
        // Extract values between semicolons
        x_pos = data.substring(1, first_semicolon).toInt();
        y_pos = data.substring(first_semicolon + 1, second_semicolon).toInt();
        theta_pos = data.substring(second_semicolon + 1).toInt();
        
        // Update position
        x = x_pos;
        y = y_pos;
        theta = theta_pos * M_PI / 180.0; // Convert degrees to radians
    }
}

void setup() {
    Serial.begin(115200);
    Serial.setTimeout(5);

    pinMode(ENC_LEFT_A_PHASE, INPUT_PULLUP);
    pinMode(ENC_LEFT_B_PHASE, INPUT_PULLUP);
    pinMode(ENC_RIGHT_A_PHASE, INPUT_PULLUP);
    pinMode(ENC_RIGHT_B_PHASE, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(ENC_LEFT_A_PHASE), changeLeft, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ENC_RIGHT_A_PHASE), changeRight, CHANGE);
}

void loop() {
    if(millis() >= lastPosUpdate + 8){
        updatePos();
    }
    getData();
}
