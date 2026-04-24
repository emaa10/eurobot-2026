#include <stdio.h>
#include "pico/stdlib.h"
#include "pullcord.h"

bool pullcordWert = false;

void pullcordInit(void)
{
    #define pullcordPin 21      //Initialiserung Pullcord

    gpio_init(pullcordPin);
    gpio_set_dir(pullcordPin, GPIO_IN);

}

bool pullcordRead()
{
    pullcordWert = false;
    static int counter = 5;  // static: bleibt zwischen Aufrufen erhalten
    pullcordWert = gpio_get(pullcordPin);

    if(pullcordWert == 0)   // 0 = Pullcord gezogen
    {
        if(counter != 0)
        {
            counter--;
        }
        if(counter == 0)    // fix: war = statt ==
        {
            return pullcordWert; //Selbes Prinzip wie bei Teamswitch -> Filterung der Werte um Prellung zu vermeiden
        }
    }
    else
    {
        counter = 5;  // zurücksetzen wenn Pullcord nicht gezogen
    }
    return pullcordWert;
}
