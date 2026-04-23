#include <stdio.h>
#include "pico/stdlib.h"

#include "hardware/timer.h"

#include "tof.h"
#include "motor.h"
#include "servo.h"
#include "pullcord.h"
#include "teamswitch.h"

int SIMA_number = 2;        //SIMA Nummer
bool programm_ende = false; //Programm zuende?
int spielzeit = 0;     //Spielzeit (100s)
bool timer_aufruf = false;  

bool general_timer(struct repeating_timer *t)
{
    timer_aufruf = true;
    return timer_aufruf;    //Timer gibt alle 1ms true aus
}

int main()
{
    stdio_init_all();

    vl53Init();         //Initialisierung ToFs
    motorInit();        //Initialisierung Motoren
    servoInit();        //Initialisierung Servo
    pullcordInit();     //Initialisierung Pullcord
    teamswitchInit();   //Initialisierung Teamswitch + LEDs

    struct repeating_timer timer_t; 
    add_repeating_timer_ms(-1, general_timer, NULL, &timer_t);  //Hinzufügen Timer

    while(programm_ende == false)
    {
        if(timer_aufruf == true)
        {
            teamswitchRead();   //Teamswitch auslesen
            pullcordRead();     //Pullcord auslesen
            spielzeit = spielzeit ++;   //Spielzeit hochzählen

            uint16_t d1 = vl53_read_distance(i2c1); //Distanz 1 auslesen
            uint16_t d2 = vl53_read_distance(i2c0); //Distanz 2 auslesen
            if(spielzeit >= 85000)
            {
                getDistancemm(d1, d2);
                drive();   //wenn <= 15s Spielzeit übrig sind -> fahren
            }
            if(spielzeit >= 100000)
            {
                blockMotors();  //nach Ablauf der Spielzeit: Motoren disablen und Servo drehen
                servoTurn();
            }
        }
        
    }

}
