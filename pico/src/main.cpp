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
const int tPerStep = 


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

//sets servo to pos 0
void homeServo(Servo servo) {
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

void stepperDrive(unsigned int steps, bool dir, int pinDir, int pinStep) {
    digitalWrite(pinDir, dir ? 0 : 1);
    delay(10);
    for (unsigned int i = 0; i < steps; i++) {
        digitalWrite(right_stepper_STEP, HIGH);
        digitalWrite(left_stepper_STEP, HIGH);
        delayMicroseconds(timePerStep);
    }
}

//drives one direction until switch 1 activates
void homeStepper1() {
    while(digitalRead(SWITCH1) == LOW) { //solange nicht ausgelöst

    }
}

// nur serial init, warten dann auf setup command von raspi
void setup() {
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
}

void loop() {
    delay(1000);
}
