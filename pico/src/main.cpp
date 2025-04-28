#include <Arduino.h>
#include <Servo.h>

Servo servo_DRIVE_LEFT;
Servo servo_PLATE_GRIPPER;
Servo servo_DRIVE_FLAG;
Servo servo4;
Servo servo5;
Servo servo6;
Servo servo7;
Servo servo8;

/*              GLOBALS            */
const int tPerStep = 1200;//800
int RIGHT_currentPosStepper = 0;
int MID_currentPosStepper = 0;
int RIGHT_targetPosStepper = 0;
int MID_targetPosStepper = 0;
bool stepperMoveActive = false;


/*              PINS            */
#define RIGHT_STEPPER_EN 18
#define RIGHT_STEPPER_DIR 16
#define RIGHT_STEPPER_STEP 17
#define MID_STEPPER_EN 21   
#define MID_STEPPER_DIR 19  
#define MID_STEPPER_STEP 20 

#define SWITCH1 13 // backup
#define SWITCH2 14 // -> MID_stepper
#define SWITCH3 15 // -> RIGHT_stepper

#define SERVO_DRIVE_LEFT 2
#define SERVO_PLATE_GRIPPER 3
#define SERVO_DRIVE_FLAG 6
#define SERVO4 7
#define SERVO5 8
#define SERVO6 9
#define SERVO7 10       //backup: 11
#define SERVO8 11

// ========== motor functions ==========

//sets servo to pos 0
void homeServo(Servo &servo) {
    servo.write(0);
}

//homes all servos
void homeServos() {
    servo_DRIVE_LEFT.write(0);
    servo_PLATE_GRIPPER.write(0);
    servo_DRIVE_FLAG.write(20);
    servo4.write(0);
    servo5.write(0);
    servo6.write(0);
    servo7.write(0);
    servo8.write(0);
}

void processSteppers() {
    static unsigned long lastStepTime = 0;
    if (!stepperMoveActive) return;

    unsigned long now = micros();
    if (now - lastStepTime < tPerStep * 2) return;
    lastStepTime = now;

    if (RIGHT_currentPosStepper != RIGHT_targetPosStepper) {
        bool dir = RIGHT_currentPosStepper < RIGHT_targetPosStepper;
        digitalWrite(RIGHT_STEPPER_DIR, dir);
        digitalWrite(RIGHT_STEPPER_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(RIGHT_STEPPER_STEP, LOW);
        delayMicroseconds(tPerStep);
        RIGHT_currentPosStepper += dir ? 1 : -1;
    }

    if (MID_currentPosStepper != MID_targetPosStepper) {
        bool dir = MID_currentPosStepper < MID_targetPosStepper;
        digitalWrite(MID_STEPPER_DIR, dir);
        digitalWrite(MID_STEPPER_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(MID_STEPPER_STEP, LOW);
        delayMicroseconds(tPerStep);
        MID_currentPosStepper += dir ? 1 : -1;
    }

    // Beide Stepper fertig?
    if (RIGHT_currentPosStepper == RIGHT_targetPosStepper && MID_currentPosStepper == MID_targetPosStepper) {
        stepperMoveActive = false;
        Serial.println("ok");
    }
}

//drives one direction until switch 1 activates
void RIGHT_homeStepper() {
    digitalWrite(RIGHT_STEPPER_DIR, LOW);
    while(digitalRead(SWITCH1) == HIGH) {
        digitalWrite(RIGHT_STEPPER_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(RIGHT_STEPPER_STEP, LOW);
        delayMicroseconds(tPerStep);
    }

    delay(100);

    digitalWrite(RIGHT_STEPPER_DIR, HIGH);
    for(int i = 0; i < 10;i++){
        digitalWrite(RIGHT_STEPPER_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(RIGHT_STEPPER_STEP, LOW);
        delayMicroseconds(tPerStep);
    }

    RIGHT_currentPosStepper = 0;
}

void MID_homeStepper() {
    digitalWrite(MID_STEPPER_DIR, HIGH); //might need change
    while(digitalRead(SWITCH2) == HIGH) {
        digitalWrite(MID_STEPPER_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(MID_STEPPER_STEP, LOW);
        delayMicroseconds(tPerStep);
    }
    MID_currentPosStepper = 0;
}

// Emergency Stop: stop all motors immediately
void emergencyStop() {
    stepperMoveActive = false;
    digitalWrite(RIGHT_STEPPER_EN, HIGH);
    digitalWrite(MID_STEPPER_EN, HIGH);
    servo_DRIVE_LEFT.detach();
    servo_PLATE_GRIPPER.detach();
    servo_DRIVE_FLAG.detach();
    servo4.detach();
    servo5.detach();
    servo6.detach();
    servo7.detach();
    servo8.detach();
    Serial.println("stopped");
}

// ========== setup / loop ==========

// run if ready
void startupRoutine() {
    homeServos();
    // RIGHT_homeStepper();
    // MID_homeStepper();
    Serial.println("ok");
}

// nur serial init, warten dann auf setup command von raspi
void setup() {
    Serial.begin(115200);
    
    pinMode(25, OUTPUT);

    pinMode(RIGHT_STEPPER_DIR, OUTPUT);
    pinMode(RIGHT_STEPPER_EN, OUTPUT);
    pinMode(RIGHT_STEPPER_STEP, OUTPUT);
    pinMode(MID_STEPPER_DIR, OUTPUT);
    pinMode(MID_STEPPER_EN, OUTPUT);
    pinMode(MID_STEPPER_STEP, OUTPUT);

    pinMode(SWITCH1, INPUT_PULLUP);
    pinMode(SWITCH2, INPUT_PULLUP);
    pinMode(SWITCH3, INPUT_PULLUP);

    // Enable steppers (LOW = enabled)
    digitalWrite(RIGHT_STEPPER_EN, HIGH);
    digitalWrite(MID_STEPPER_EN, HIGH);

    servo_DRIVE_LEFT.attach(SERVO_DRIVE_LEFT, 700, 2600);
    servo_PLATE_GRIPPER.attach(SERVO_PLATE_GRIPPER, 700, 2600);
    servo_DRIVE_FLAG.attach(SERVO_DRIVE_FLAG, 700, 2600);
    servo4.attach(SERVO4);
    servo5.attach(SERVO5);
    servo6.attach(SERVO6);
    servo7.attach(SERVO7);
    servo8.attach(SERVO8);

    startupRoutine();

}

void loop() {
    /*if (Serial.available()) {
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
            case 'a': 
                digitalWrite(RIGHT_STEPPER_EN, LOW);
                RIGHT_targetPosStepper = value;
                stepperMoveActive = true;
                success = true; 
                break;
            case 'b': 
                digitalWrite(MID_STEPPER_EN, LOW);
                MID_targetPosStepper = value;
                stepperMoveActive = true;
                success = true; 
                break;
            case 's': servo_DRIVE_LEFT.attach(SERVO_DRIVE_LEFT); servo_DRIVE_LEFT.write(value); success = true; break;
            case 't': servo_PLATE_GRIPPER.attach(SERVO_PLATE_GRIPPER); servo_PLATE_GRIPPER.write(value); success = true; break;
            case 'u': servo_DRIVE_FLAG.attach(SERVO_DRIVE_FLAG); servo_DRIVE_FLAG.write(value); success = true; break;
            case 'v': servo4.attach(SERVO4); servo4.write(value); success = true; break;
            case 'w': servo5.attach(SERVO5); servo5.write(value); success = true; break;
            case 'x': servo6.attach(SERVO6); servo6.write(value); success = true; break;
            case 'y': servo7.attach(SERVO7); servo7.write(value); success = true; break;
            case 'h': startupRoutine(); success = true; break;
            case 'e': // Emergency stop command: send "e0"
                emergencyStop(); 
                success = true;
                break;
            default: success = false;
        }

        if (!success) {
            Serial.println("f");
        } else {
            if (device != 'e') Serial.println("ok");
        }
    }
    processSteppers();
    */
//    servo_DRIVE_FLAG.write(20);
//    delay(1000);
//    servo_PLATE_GRIPPER.write(65);
//    delay(1000);
//    servo_PLATE_GRIPPER.write(180);
//    delay(1000);
   servo_PLATE_GRIPPER.write(180);
   delay(1000);

}