#include <Arduino.h>
#include <Servo.h>
#include <AccelStepper.h>

// Define the stepper motor connections
#define RIGHT_STEPPER_EN 18
#define RIGHT_STEPPER_DIR 16
#define RIGHT_STEPPER_STEP 17
#define MID_STEPPER_EN 21   
#define MID_STEPPER_DIR 19  
#define MID_STEPPER_STEP 20 

// Define the limit switches
#define SWITCH1 13 // backup
#define SWITCH2 14 // -> MID_stepper
#define SWITCH3 15 // -> RIGHT_stepper

// Define servo pins
#define SERVO_DRIVE_LEFT 2
#define SERVO_PLATE_GRIPPER 3
#define SERVO_DRIVE_FLAG 6
#define SERVO4 7
#define SERVO5 8
#define SERVO6 9
#define SERVO7 10       //backup: 11
#define SERVO8 11

// Create servo objects
Servo servo_DRIVE_LEFT;
Servo servo_PLATE_GRIPPER;
Servo servo_DRIVE_FLAG;
Servo servo4;
Servo servo5;
Servo servo6;
Servo servo7;
Servo servo8;

// Create AccelStepper objects with driver interface
// AccelStepper::DRIVER means step/dir pins
AccelStepper rightStepper(AccelStepper::DRIVER, RIGHT_STEPPER_STEP, RIGHT_STEPPER_DIR);
AccelStepper midStepper(AccelStepper::DRIVER, MID_STEPPER_STEP, MID_STEPPER_DIR);

// Global variables
const int tPerStep = 450; // Used for manual stepping during homing
bool isHoming = false;    // Flag to indicate homing is in progress
bool stepperMoveActive = false;

// Stepper parameters
const float MAX_SPEED = 1000;      // Maximum speed in steps/second
const float ACCELERATION = 500;    // Acceleration in steps/second^2
const float HOMING_SPEED = 400;    // Speed during homing

// ========== motor functions ==========

// Sets servo to pos 0
void homeServo(Servo &servo) {
    servo.write(0);
}

// Homes all servos
void homeServos() {
    servo_DRIVE_LEFT.write(20);
    servo_PLATE_GRIPPER.write(90);
    servo_DRIVE_FLAG.write(20);
    servo4.write(0);
    servo5.write(0);
    servo6.write(0);
    servo7.write(0);
    servo8.write(0);
}

// Check if any stepper is still running
bool steppersRunning() {
    return rightStepper.isRunning() || midStepper.isRunning();
}

// Check if limit switch is activated
bool isLimitSwitchActivated(int pin) {
    return digitalRead(pin) == LOW; // LOW means switch is pressed (normally open)
}

// Home both stepper motors simultaneously
void homeSteppers() {
    // Set homing speeds and accelerations
    rightStepper.setMaxSpeed(HOMING_SPEED);
    rightStepper.setAcceleration(ACCELERATION);
    midStepper.setMaxSpeed(HOMING_SPEED);
    midStepper.setAcceleration(ACCELERATION);
    
    // Set homing direction (negative for right, positive for mid)
    rightStepper.setSpeed(-HOMING_SPEED);
    midStepper.setSpeed(HOMING_SPEED);
    
    bool rightHomed = false;
    bool midHomed = false;
    
    // Run both steppers until both hit their limit switches
    while (!rightHomed || !midHomed) {
        // Check right stepper
        if (!rightHomed) {
            if (isLimitSwitchActivated(SWITCH3)) {
                rightStepper.stop();
                rightStepper.setCurrentPosition(0);
                rightHomed = true;
                Serial.println("Right stepper hit limit switch");
            } else {
                rightStepper.runSpeed();
            }
        }
        
        // Check mid stepper
        if (!midHomed) {
            if (isLimitSwitchActivated(SWITCH2)) {
                midStepper.stop();
                midStepper.setCurrentPosition(0);
                midHomed = true;
                Serial.println("Mid stepper hit limit switch");
            } else {
                midStepper.runSpeed();
            }
        }
        
        yield(); // Allow other processes to run
    }
    
    // Both steppers have hit their limit switches
    // Now back off from switches slightly
    rightStepper.moveTo(50);  // Move 50 steps away from limit switch
    midStepper.moveTo(-50);   // Move 50 steps away from limit switch
    
    // Run both steppers simultaneously until they complete their moves
    while (rightStepper.isRunning() || midStepper.isRunning()) {
        rightStepper.run();
        midStepper.run();
        yield();
    }
    
    // Set current positions as zero
    rightStepper.setCurrentPosition(0);
    midStepper.setCurrentPosition(0);
    
    // Reset to normal speeds and accelerations
    rightStepper.setMaxSpeed(MAX_SPEED);
    rightStepper.setAcceleration(ACCELERATION);
    midStepper.setMaxSpeed(MAX_SPEED);
    midStepper.setAcceleration(ACCELERATION);
    
    Serial.println("Both steppers homed");
}

// Process stepper movements
void processSteppers() {
    // Run both steppers simultaneously
    rightStepper.run();
    midStepper.run();
    
    // Check if both steppers have completed their movement
    if (stepperMoveActive && !steppersRunning()) {
        stepperMoveActive = false;
        Serial.println("ok");
    }
}

// Emergency Stop: stop all motors immediately
void emergencyStop() {
    // Stop all stepper motors
    rightStepper.stop();
    midStepper.stop();
    stepperMoveActive = false;
    
    // Disable stepper drivers
    digitalWrite(RIGHT_STEPPER_EN, HIGH);
    digitalWrite(MID_STEPPER_EN, HIGH);
    
    // Detach all servos
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

// Run if ready
void startupRoutine() {
    homeServos();
    //Serial.println("Servos homed. Homing steppers next...");
    
    // Enable steppers
    digitalWrite(RIGHT_STEPPER_EN, LOW);
    digitalWrite(MID_STEPPER_EN, LOW);
    
    isHoming = true;
    
    // Home both steppers simultaneously
    homeSteppers();
    
    isHoming = false;
    Serial.println("ok");
}

void setup() {
    Serial.begin(115200);
    
    pinMode(25, OUTPUT);

    // Configure stepper pins
    pinMode(RIGHT_STEPPER_DIR, OUTPUT);
    pinMode(RIGHT_STEPPER_EN, OUTPUT);
    pinMode(RIGHT_STEPPER_STEP, OUTPUT);
    pinMode(MID_STEPPER_DIR, OUTPUT);
    pinMode(MID_STEPPER_EN, OUTPUT);
    pinMode(MID_STEPPER_STEP, OUTPUT);

    // Configure limit switch pins
    pinMode(SWITCH1, INPUT_PULLUP);
    pinMode(SWITCH2, INPUT_PULLUP);
    pinMode(SWITCH3, INPUT_PULLUP);

    // Enable steppers (LOW = enabled)
    digitalWrite(RIGHT_STEPPER_EN, HIGH); // Start disabled
    digitalWrite(MID_STEPPER_EN, HIGH);   // Start disabled

    // Attach servos
    servo_DRIVE_LEFT.attach(SERVO_DRIVE_LEFT, 700, 2600);
    servo_PLATE_GRIPPER.attach(SERVO_PLATE_GRIPPER, 700, 2600);
    servo_DRIVE_FLAG.attach(SERVO_DRIVE_FLAG, 700, 2600);
    servo4.attach(SERVO4);
    servo5.attach(SERVO5);
    servo6.attach(SERVO6);
    servo7.attach(SERVO7);
    servo8.attach(SERVO8);

    // Configure stepper parameters
    rightStepper.setMaxSpeed(MAX_SPEED);
    rightStepper.setAcceleration(ACCELERATION);
    midStepper.setMaxSpeed(MAX_SPEED);
    midStepper.setAcceleration(ACCELERATION);
    
    startupRoutine();
        
    // // Enable mid stepper
    // digitalWrite(MID_STEPPER_EN, LOW);
    // midStepper.setCurrentPosition(0);
    // midStepper.moveTo(1400);
    // stepperMoveActive = true;
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

}