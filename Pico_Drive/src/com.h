#pragma once
#include <Arduino.h>

// Command-Struktur shared zwischen Core 0 und Core 1
struct Command {
    int type;       // 0=Stop,1=Geradeaus,2=Drehen,3=SetSpeed,4=GetSpeed
    float arg1;
    float arg2;
    volatile bool newCmd;
    volatile bool done;
    float speedLeft;
    float speedRight;
};

class MotorCom {
public:
    MotorCom(Command* cmdPtr);
    void begin();      // startet Core 1
private:
    Command* cmd;
    static void core1LoopStatic();   // Wrapper für multicore
    void core1Loop();                // tatsächliche Loop auf Core 1
    static MotorCom* instance;       // Singleton für Core 1
};
