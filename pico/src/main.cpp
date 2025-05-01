#include <Arduino.h>
#include <Servo.h>
#include <AccelStepper.h>

#define RIGHT_STEPPER_EN 18
#define RIGHT_STEPPER_DIR 16
#define RIGHT_STEPPER_STEP 17
#define MID_STEPPER_EN 21   
#define MID_STEPPER_DIR 19  
#define MID_STEPPER_STEP 20 

#define SWITCH1 15 // backup
#define SWITCH2 14 // -> MID_stepper
#define SWITCH3 13 // -> RIGHT_stepper

#define SERVO_DRIVE_LEFT 2
#define SERVO_PLATE_GRIPPER 3
#define SERVO_DRIVE_FLAG 6
#define SERVO_GRIP_RIGHT 7
#define SERVO_ROTATE_RIGHT 8
#define SERVO_ROTATE_LEFT 9
#define SERVO_GRIP_LEFT 10       //backup: 11
#define SERVO8 11

Servo servo_DRIVE_LEFT;
Servo servo_PLATE_GRIPPER;
Servo servo_DRIVE_FLAG;
Servo servo_GRIP_RIGHT;
Servo servo_ROTATE_RIGHT;
Servo servo_ROTATE_LEFT;
Servo servo_GRIP_LEFT;
Servo servo8;

// AccelStepper::DRIVER means step/dir pins
AccelStepper rightStepper(AccelStepper::DRIVER, RIGHT_STEPPER_STEP, RIGHT_STEPPER_DIR);
AccelStepper midStepper(AccelStepper::DRIVER, MID_STEPPER_STEP, MID_STEPPER_DIR);

bool isHoming = false;    // Flag to indicate homing is in progress
bool stepperMoveActive = false;
bool pendingStepperResponse = false;  // Flag to track if we need to send "ok" after steppers finish

const float MAX_SPEED = 1300;      
const float ACCELERATION = 100000;   
const float HOMING_SPEED = 1000;    

int RIGHT_stepperTargetPos = 0;
int MID_stepperTargetPos = 0;

int RIGHT_stepperStartPos = 350;
int MID_stepperStartPos = 1500;

bool startupRoutineBool = false;


// ========== motor position functions ==========

void servoDriveLeftUp(){
    servo_DRIVE_LEFT.write(0);
}

void servoDriveLeftDown(){
    servo_DRIVE_LEFT.write(180);
}

void servoPlateGripperFullyOpen(){
    servo_PLATE_GRIPPER.write(180);
}

void servoPlateGripperGripPlate(){
    servo_PLATE_GRIPPER.write(120);
}

void servoPlateGripperColisionAvoidence(){
    servo_PLATE_GRIPPER.write(130);
}

void servoPlateGripperClosed(){
    servo_PLATE_GRIPPER.write(0);
}

void servoDriveFlagUP(){
    servo_DRIVE_FLAG.write(20);
}

void servoDriveFlagDown(){
    servo_DRIVE_FLAG.write(165);
}

void servoGripRightClosed(){
    servo_GRIP_RIGHT.write(20);
}

void servoGripRightOpen(){
    servo_GRIP_RIGHT.write(60);
}

void servoRotateRightOutwards(){
    servo_ROTATE_RIGHT.write(20);
}

void servoRotateRightInwards(){
    servo_ROTATE_RIGHT.write(180);
}

void servoRotateRightDeposit(){
    servo_ROTATE_RIGHT.write(165);
}

void servoRotateRightMid(){
    servo_ROTATE_RIGHT.write(100);
}

// ========== motor functions ==========

//refer to look up table for servo positions
void colisionFreeServos() {
    servoDriveLeftDown();
    servoPlateGripperColisionAvoidence(); // weit vor sodass arm nicht aufsetzt
    servoDriveFlagUP(); // ganz hoch, dann muss später nichtmehr gehomed werden
    servo_GRIP_RIGHT.write(20);
    servo_ROTATE_RIGHT.write(50);
    servo_ROTATE_LEFT.write(120);
    servo_GRIP_LEFT.write(100);
    servo8.write(0);
}

void positionServos() {
    servoPlateGripperClosed();// weit vor sodass arm nicht aufsetzt
    servo_GRIP_RIGHT.write(60);
    servo_ROTATE_RIGHT.write(50);
    servo_ROTATE_LEFT.write(130);
    servo_GRIP_LEFT.write(100);
    servo8.write(0);
}


bool steppersRunning() {
    return rightStepper.isRunning() || midStepper.isRunning();
}

void homeSteppers() {   
    rightStepper.setSpeed(-HOMING_SPEED);
    midStepper.setSpeed(-HOMING_SPEED);
    
    bool rightHomed = false;
    bool midHomed = false;
    
    while (!rightHomed || !midHomed) {
        
        if (!rightHomed) {
            if (!digitalRead(SWITCH3)) {
                rightStepper.stop();
                rightStepper.setCurrentPosition(0);
                rightHomed = true;
            } else {
                rightStepper.runSpeed();
            }
        }
        
        if (!midHomed) {
            if (!digitalRead(SWITCH2)) {
                midStepper.stop();
                midStepper.setCurrentPosition(0);
                midHomed = true;
            } else {
                midStepper.runSpeed();
            }
        }
    }
    
    delay(50);

    rightStepper.moveTo(20); 
    midStepper.moveTo(100); 
    
    while (rightStepper.isRunning() || midStepper.isRunning()) {
        rightStepper.run();
        midStepper.run();
    }   
    
    rightStepper.setMaxSpeed(MAX_SPEED/2);
    midStepper.setMaxSpeed(MAX_SPEED);
}

void positionSteppers() {
    MID_stepperTargetPos = MID_stepperStartPos;
    midStepper.moveTo(MID_stepperTargetPos); 

    while(midStepper.isRunning()) {
        midStepper.run();
    }   
    RIGHT_stepperTargetPos = RIGHT_stepperStartPos;
    rightStepper.moveTo(RIGHT_stepperTargetPos); 
    
    while (rightStepper.isRunning()) {
        rightStepper.run();
    }    
}

void startupRoutine() {
    Serial.println("startup routine");
    colisionFreeServos();
    
    digitalWrite(RIGHT_STEPPER_EN, LOW);
    digitalWrite(MID_STEPPER_EN, LOW);
    
    isHoming = true;
    
    homeSteppers();

    positionSteppers();

    positionServos();
    
    isHoming = false;
    startupRoutineBool = false;
    Serial.println("ok");
}

void processSteppers() {
    if(startupRoutineBool){
        startupRoutine();
    }
    rightStepper.moveTo(RIGHT_stepperTargetPos); 
    midStepper.moveTo(MID_stepperTargetPos);

    rightStepper.run();
    midStepper.run();
    
    // Check if steppers were running and now have stopped
    if (stepperMoveActive && !steppersRunning()) {
        stepperMoveActive = false;
        
        // Send "ok" only when steppers have finished their movement
        if (pendingStepperResponse) {
            Serial.println("ok");
            pendingStepperResponse = false;
        }
    }
}

void reinitializeServos() {
    servo_DRIVE_LEFT.attach(SERVO_DRIVE_LEFT, 700, 2600);
    servo_PLATE_GRIPPER.attach(SERVO_PLATE_GRIPPER, 700, 2600);
    servo_DRIVE_FLAG.attach(SERVO_DRIVE_FLAG, 700, 2600);
    servo_GRIP_RIGHT.attach(SERVO_GRIP_RIGHT, 700, 2600);
    servo_ROTATE_RIGHT.attach(SERVO_ROTATE_RIGHT, 700, 2600);
    servo_ROTATE_LEFT.attach(SERVO_ROTATE_LEFT);
    servo_GRIP_LEFT.attach(SERVO_GRIP_LEFT);
    servo8.attach(SERVO8);
}

void emergencyStop() {
    rightStepper.stop();
    midStepper.stop();
    stepperMoveActive = false;
    pendingStepperResponse = false;
    
    digitalWrite(RIGHT_STEPPER_EN, HIGH);
    digitalWrite(MID_STEPPER_EN, HIGH);
    
    servo_DRIVE_LEFT.detach();
    servo_PLATE_GRIPPER.detach();
    servo_DRIVE_FLAG.detach();
    servo_GRIP_RIGHT.detach();
    servo_ROTATE_RIGHT.detach();
    servo_ROTATE_LEFT.detach();
    servo_GRIP_LEFT.detach();
    servo8.detach();
    
    Serial.println("ok");
}

// ========== setup / loop ==========

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
    digitalWrite(RIGHT_STEPPER_EN, HIGH); // Start disabled
    digitalWrite(MID_STEPPER_EN, HIGH);   // Start disabled

    servo_DRIVE_LEFT.attach(SERVO_DRIVE_LEFT, 700, 2600);
    servo_PLATE_GRIPPER.attach(SERVO_PLATE_GRIPPER, 700, 2600);
    servo_DRIVE_FLAG.attach(SERVO_DRIVE_FLAG, 700, 2600);
    servo_GRIP_RIGHT.attach(SERVO_GRIP_RIGHT, 700, 2600);
    servo_ROTATE_RIGHT.attach(SERVO_ROTATE_RIGHT, 700, 2600);
    servo_ROTATE_LEFT.attach(SERVO_ROTATE_LEFT);
    servo_GRIP_LEFT.attach(SERVO_GRIP_LEFT);
    servo8.attach(SERVO8);

    rightStepper.setMaxSpeed(MAX_SPEED);
    rightStepper.setAcceleration(ACCELERATION);
    midStepper.setMaxSpeed(MAX_SPEED);
    midStepper.setAcceleration(ACCELERATION);
    
    startupRoutine();
    // servoGripRightClosed();
    // servoRotateRightOutwards();
    // servoDriveFlagUP();
}

void loop() {
    processSteppers();
}

void setup1(){
}

void loop1(){
    digitalWrite(25, millis() / 500 % 2);

    if (Serial.available()) {
        String command = Serial.readStringUntil('\n'); 
        command.trim();

        // if (command.length() < 2) {
        //     Serial.println("f");
        //     return;
        // }

        char device = command.charAt(0);
        int value = command.substring(1).toInt();
        Serial.println(value);

        bool success = false;

        switch (device) {
            case 'a': 
                digitalWrite(RIGHT_STEPPER_EN, LOW);
                RIGHT_stepperTargetPos = value;
                stepperMoveActive = true;
                pendingStepperResponse = true;  // Set flag to indicate response should be sent after movement
                success = true; 
                break;
            case 'b': 
                digitalWrite(MID_STEPPER_EN, LOW);
                MID_stepperTargetPos = value;
                stepperMoveActive = true;
                pendingStepperResponse = true;  // Set flag to indicate response should be sent after movement
                success = true; 
                break;
            case 'r': servo_DRIVE_LEFT.write(value); success = true; break;
            case 's': servo_PLATE_GRIPPER.write(value); success = true; break;
            case 't': servo_DRIVE_FLAG.write(value); success = true; break;
            case 'u': servo_DRIVE_FLAG.write(value); success = true; break;
            case 'v': servo_GRIP_RIGHT.write(value); success = true; break;
            case 'w': servo_ROTATE_RIGHT.write(value); success = true; break;
            case 'x': servo_ROTATE_LEFT.write(value); success = true; break;
            case 'y': servo_GRIP_LEFT.write(value); success = true; break;
            case 'h': startupRoutineBool = true; success = true; break;
            case 'i': reinitializeServos(); success = true; break;
            case 'e':
                emergencyStop(); 
                success = true;
                break;
            default: success = false;
        }

        if (!success) {
            Serial.println("f");
        } 
    }
}