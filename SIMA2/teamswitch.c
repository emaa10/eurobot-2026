#include <stdio.h>
#include "pico/stdlib.h"
#include "teamswitch.h"

bool switchState = false;   

void teamswitchInit()
{
    #define teamswitch 16

    gpio_init(teamswitch);              //Initialisierung Teamswitch
    gpio_set_dir(teamswitch, GPIO_IN);

    //LEDs
    #define LED_blue 17
    #define LED_yellow 14

    gpio_init(LED_blue);                //Initialisierung LEDs (blau/gelb)
    gpio_set_dir(LED_blue, GPIO_OUT);

    gpio_init(LED_yellow);
    gpio_set_dir(LED_yellow, GPIO_OUT);
}

void ledBlueOn()
{
    gpio_put(LED_blue, 0);               //LED blau anschalten
}

void ledBlueOf()
{
    gpio_put(LED_blue, 1);              //LED blau ausschalten
}

void ledYellowOn()
{
    gpio_put(LED_yellow, 0);            //LED gelb anschalten
}

void ledYellowOf()
{
    gpio_put(LED_yellow, 1);            //LED gelb ausschalten
}

bool teamswitchRead()
{
    switchState = false;
    int counterBlue = 5;
    int counterYellow = 5;
    switchState = gpio_get(teamswitch);  //Teamswitch auslesen
    if(switchState == 0)
    {
        if(counterYellow != 0)
        {
            counterYellow = counterYellow --;
        }
        if(counterYellow == 0)
        {
            ledYellowOn();      //Filterung der Werte um Prellung des Schalters zu vermeiden
            ledBlueOf();        //erst nach 5 entsprechenden Werten
            return switchState; //LEDs an/aus        
        }
    }
    if(switchState == 1)
    {
        if(counterBlue != 0)
        {
            counterBlue = counterBlue --;
        }
        if(counterBlue == 0)
        {
            ledBlueOn();        //selbes hier (1 = Team gelb, 0 = Team blau)
            ledYellowOf();
            return switchState;
        }
    }
}