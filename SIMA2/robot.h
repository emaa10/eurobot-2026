#pragma once

// Vorwärts fahren (mm > 0) oder rückwärts (mm < 0).
// Blockiert bis fertig. Pausiert automatisch bei Gegner.
void driveMM(int mm);

// Drehen: deg > 0 = rechts, deg < 0 = links.
// Blockiert bis fertig. Pausiert automatisch bei Gegner.
void turnDeg(int deg);

// Interna — von main.cpp aufgerufen
void robotInitMotors();
void robotInitTof();
void robotPollTof();     // im Core0-Loop aufrufen (alle 20ms)
