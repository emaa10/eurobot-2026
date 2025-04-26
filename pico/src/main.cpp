#include <Arduino.h>
#include <Servo.h>

Servo servo1;
Servo servo2;
Servo servo3;
Servo servo4;
Servo servo5;
Servo servo6;
Servo servo7;

/*              GLOBALS            */
const int tPerStep = 800;
int currentPosStepper1 = 0;
int currentPosStepper2 = 0;


/*              PINS            */
#define STEPPER1_EN 17
#define STEPPER1_DIR 26
#define STEPPER1_STEP 27
#define STEPPER2_EN 21   //backup: 16
#define STEPPER2_DIR 20  //backup: 17
#define STEPPER2_STEP 19 //backup: 18

#define SWITCH1 15 // -> stepper1
#define SWITCH2 14 // -> stepper2
#define SWITCH3 13 // backup

#define SERVO1 2
#define SERVO2 3
#define SERVO3 6
#define SERVO4 7
#define SERVO5 8
#define SERVO6 9
#define SERVO7 10       //backup: 11

// ========== motor functions ==========

//sets servo to pos 0
void homeServo(Servo &servo) {
    servo.write(0);
}

//homes all servos
void homeServos() {
    servo1.write(0);
    servo2.write(0);
    servo3.write(0);
    servo4.write(0);
    servo5.write(0);
    servo6.write(0);
    servo7.write(0);
}

void stepperDrive1(int newPos) {
    bool dir = (currentPosStepper1 < newPos);
    digitalWrite(STEPPER1_DIR, dir);
    delay(10);

    int steps = abs(newPos - currentPosStepper1);
    for (unsigned int i = 0; i < steps; i++) {
        digitalWrite(STEPPER1_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(STEPPER1_STEP, LOW);
        delayMicroseconds(tPerStep);
        currentPosStepper1 += dir ? 1 : -1;
    }
}

void stepperDrive2(int newPos) {
    bool dir = (currentPosStepper2 < newPos);
    digitalWrite(STEPPER2_DIR, dir);
    delay(10);

    int steps = abs(newPos - currentPosStepper2);
    for (unsigned int i = 0; i < steps; i++) {
        digitalWrite(STEPPER2_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(STEPPER2_STEP, LOW);
        delayMicroseconds(tPerStep);
        currentPosStepper2 += dir ? 1 : -1; 
    }
}

//drives one direction until switch 1 activates
void homeStepper1() {
    digitalWrite(STEPPER1_DIR, HIGH); //might need change
    while(digitalRead(SWITCH1) == LOW) { //solange nicht ausgelöst
        digitalWrite(STEPPER1_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(STEPPER1_STEP, LOW);
        delayMicroseconds(tPerStep);
    }
    currentPosStepper1 = 0;
}

void homeStepper2() {
    digitalWrite(STEPPER2_DIR, HIGH); //might need change
    while(digitalRead(SWITCH2) == LOW) { //solange nicht ausgelöst
        digitalWrite(STEPPER2_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(STEPPER2_STEP, LOW);
        delayMicroseconds(tPerStep);
    }
    currentPosStepper2 = 0;
}

// ========== setup / loop ==========

// run if ready
void startupRoutine() {
    homeServos();
    homeStepper1();
    homeStepper2();
    Serial.println("ok");
}

// nur serial init, warten dann auf setup command von raspi
void setup() {
    Serial.begin(115200);

    pinMode(STEPPER1_DIR, OUTPUT);
    pinMode(STEPPER1_EN, OUTPUT);
    pinMode(STEPPER1_STEP, OUTPUT);
    pinMode(STEPPER2_DIR, OUTPUT);
    pinMode(STEPPER2_EN, OUTPUT);
    pinMode(STEPPER2_STEP, OUTPUT);
    pinMode(STEPPER2_STEP, OUTPUT);

    pinMode(SWITCH1, INPUT_PULLUP);
    pinMode(SWITCH2, INPUT_PULLUP);

    digitalWrite(STEPPER1_EN, LOW);
    digitalWrite(STEPPER2_EN, LOW);


    servo1.attach(SERVO1);
    servo2.attach(SERVO2);
    servo3.attach(SERVO3);
    servo4.attach(SERVO4);
    servo5.attach(SERVO5);
    servo6.attach(SERVO6);
    servo7.attach(SERVO7);
    delay(1000);
    //startupRoutine();
}

void loop() {
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n'); 
        command.trim();

        if (command.length() < 2) {
            Serial.println("f");
            return;
        }

        char device = command.charAt(0);
        int value = command.substring(1).toInt();

        bool success = false;

        switch (device) {
            case 'a': stepperDrive1(value); success = true; break;
            case 'b': stepperDrive2(value); success = true; break;
            case 's': servo1.write(value); success = true; break;
            case 't': servo2.write(value); success = true; break;
            case 'u': servo3.write(value); success = true; break;
            case 'v': servo4.write(value); success = true; break;
            case 'w': servo5.write(value); success = true; break;
            case 'x': servo6.write(value); success = true; break;
            case 'y': servo7.write(value); success = true; break;
            case 'h': startupRoutine(); success = true; break;
            default: success = false;
        }

        if (success) {
            Serial.println("ok");
        } else {
            Serial.println("f");
        }
    }
}