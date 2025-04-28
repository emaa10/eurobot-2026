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
int targetPosStepper1 = 0;
int targetPosStepper2 = 0;
bool stepperMoveActive = false;


/*              PINS            */
#define STEPPER1_EN 18
#define STEPPER1_DIR 16
#define STEPPER1_STEP 17
#define STEPPER2_EN 21   
#define STEPPER2_DIR 19  
#define STEPPER2_STEP 20 

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

void processSteppers() {
    static unsigned long lastStepTime = 0;
    if (!stepperMoveActive) return;

    unsigned long now = micros();
    if (now - lastStepTime < tPerStep * 2) return;
    lastStepTime = now;

    if (currentPosStepper1 != targetPosStepper1) {
        bool dir = currentPosStepper1 < targetPosStepper1;
        digitalWrite(STEPPER1_DIR, dir);
        digitalWrite(STEPPER1_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(STEPPER1_STEP, LOW);
        delayMicroseconds(tPerStep);
        currentPosStepper1 += dir ? 1 : -1;
    }

    if (currentPosStepper2 != targetPosStepper2) {
        bool dir = currentPosStepper2 < targetPosStepper2;
        digitalWrite(STEPPER2_DIR, dir);
        digitalWrite(STEPPER2_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(STEPPER2_STEP, LOW);
        delayMicroseconds(tPerStep);
        currentPosStepper2 += dir ? 1 : -1;
    }

    // Beide Stepper fertig?
    if (currentPosStepper1 == targetPosStepper1 && currentPosStepper2 == targetPosStepper2) {
        stepperMoveActive = false;
        Serial.println("ok");
    }
}

//drives one direction until switch 1 activates
void homeStepper1() {
    digitalWrite(STEPPER1_DIR, HIGH); //might need change
    while(digitalRead(SWITCH1) == LOW) {
        digitalWrite(STEPPER1_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(STEPPER1_STEP, LOW);
        delayMicroseconds(tPerStep);
    }
    currentPosStepper1 = 0;
}

void homeStepper2() {
    digitalWrite(STEPPER2_DIR, HIGH); //might need change
    while(digitalRead(SWITCH2) == LOW) {
        digitalWrite(STEPPER2_STEP, HIGH);
        delayMicroseconds(tPerStep);
        digitalWrite(STEPPER2_STEP, LOW);
        delayMicroseconds(tPerStep);
    }
    currentPosStepper2 = 0;
}

// Emergency Stop: stop all motors immediately
void emergencyStop() {
    stepperMoveActive = false;
    digitalWrite(STEPPER1_EN, HIGH);
    digitalWrite(STEPPER2_EN, HIGH);
    servo1.detach();
    servo2.detach();
    servo3.detach();
    servo4.detach();
    servo5.detach();
    servo6.detach();
    servo7.detach();
    Serial.println("stopped");
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
    
    pinMode(25, OUTPUT);

    pinMode(STEPPER1_DIR, OUTPUT);
    pinMode(STEPPER1_EN, OUTPUT);
    pinMode(STEPPER1_STEP, OUTPUT);
    pinMode(STEPPER2_DIR, OUTPUT);
    pinMode(STEPPER2_EN, OUTPUT);
    pinMode(STEPPER2_STEP, OUTPUT);

    pinMode(SWITCH1, INPUT_PULLUP);
    pinMode(SWITCH2, INPUT_PULLUP);

    // Enable steppers (LOW = enabled)
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
                digitalWrite(STEPPER1_EN, LOW);
                targetPosStepper1 = value;
                stepperMoveActive = true;
                success = true; 
                break;
            case 'b': 
                digitalWrite(STEPPER2_EN, LOW);
                targetPosStepper2 = value;
                stepperMoveActive = true;
                success = true; 
                break;
            case 's': servo1.attach(SERVO1); servo1.write(value); success = true; break;
            case 't': servo2.attach(SERVO2); servo2.write(value); success = true; break;
            case 'u': servo3.attach(SERVO3); servo3.write(value); success = true; break;
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
   for (int i = 0; i <= 100; i++) {
    digitalWrite(STEPPER1_STEP, HIGH);
    digitalWrite(STEPPER2_STEP, HIGH);
    delayMicroseconds(1200);
    digitalWrite(STEPPER1_STEP, LOW);
    digitalWrite(STEPPER2_STEP, LOW);
    delayMicroseconds(1200);
   }
   digitalWrite(STEPPER1_DIR, HIGH);
   digitalWrite(STEPPER2_DIR, HIGH);
   for (int i = 0; i <= 100; i++) {
    digitalWrite(STEPPER1_STEP, HIGH);
    digitalWrite(STEPPER2_STEP, HIGH);
    delayMicroseconds(1200);
    digitalWrite(STEPPER1_STEP, LOW);
    digitalWrite(STEPPER2_STEP, LOW);
    delayMicroseconds(1200);
   }
   digitalWrite(25, HIGH);
   /*for(int i = 0; i <= 180; i++) {
    delay(10);
    servo1.write(i);
    servo2.write(i);
    servo3.write(i);
    servo4.write(i);
    servo5.write(i);
   }*/
   while (true)
   {
    delay(10);
    /* code */
   }
   
}