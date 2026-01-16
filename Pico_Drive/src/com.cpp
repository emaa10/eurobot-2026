#include "com.h"
#include <pico/multicore.h>

MotorCom* MotorCom::instance = nullptr;

MotorCom::MotorCom(Command* cmdPtr) {
    cmd = cmdPtr;
    instance = this;
}

void MotorCom::begin() {
    multicore_launch_core1(core1LoopStatic);
}

// Wrapper für Core1
void MotorCom::core1LoopStatic() {
    if (instance) instance->core1Loop();
}

// Core1 Loop: UART-Kommunikation
void MotorCom::core1Loop() {
    Serial1.begin(115200);

    while (true) {
        if (Serial1.available()) {
            String line = Serial1.readStringUntil('\n');

            if (line.startsWith("F")) { // Geradeaus
                float speed = line.substring(2).toFloat();
                cmd->type = 1;
                cmd->arg1 = speed;
                cmd->newCmd = true;
            } else if (line.startsWith("T")) { // Drehen
                float speed = line.substring(2).toFloat();
                cmd->type = 2;
                cmd->arg1 = speed;
                cmd->newCmd = true;
            } else if (line.startsWith("S")) { // SetSpeed
                int space = line.indexOf(' ');
                float s1 = line.substring(2, space).toFloat();
                float s2 = line.substring(space+1).toFloat();
                cmd->type = 3;
                cmd->arg1 = s1;
                cmd->arg2 = s2;
                cmd->newCmd = true;
            } else if (line.startsWith("G")) { // Geschwindigkeit abfragen
                cmd->type = 4;
                cmd->newCmd = true;
            }

            // Warten bis Core0 fertig
            while (!cmd->done) delay(1);
            cmd->done = false;

            // Antwort zurück
            Serial1.print("OK");
            if (cmd->type == 4) {
                Serial1.print(" ");
                Serial1.print(cmd->speedLeft);
                Serial1.print(" ");
                Serial1.println(cmd->speedRight);
            } else {
                Serial1.println();
            }
        }
    }
}
