#include <Arduino.h>

#define stepRight 4
#define stepLeft 8
#define ENLeft 6
#define ENRight 10

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(stepLeft, OUTPUT);
  pinMode(stepRight, OUTPUT);
  pinMode(ENRight, OUTPUT);
  pinMode(ENLeft, OUTPUT);
  digitalWrite(ENLeft, LOW);
  digitalWrite(ENRight, LOW);
}
void drive(int stepintervall) {
  digitalWrite(stepLeft, HIGH);
  digitalWrite(stepRight, HIGH);
  delayMicroseconds(600);
  digitalWrite(stepLeft, LOW);
  digitalWrite(stepRight, LOW);
  delayMicroseconds(600);  

}

void loop() {
  // put your main code here, to run repeatedly:
  drive(600);
}
