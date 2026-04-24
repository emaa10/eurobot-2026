#include "robot.h"

// ════════════════════════════════════════════════════════════
//  TAKTIK — hier schreiben
//
//  driveMM(mm)   Vorwärts (mm > 0) oder rückwärts (mm < 0)
//  turnDeg(deg)  Rechts (deg > 0) oder links (deg < 0)
//
//  Beide Funktionen blockieren bis fertig und pausieren
//  automatisch wenn ein Gegner erkannt wird.
// ════════════════════════════════════════════════════════════

void runTactic() {
    driveMM(1000);     // 1 m vorwärts
    turnDeg(90);       // 90° rechts
    driveMM(500);      // 50 cm vorwärts
    turnDeg(-90);      // 90° links
    driveMM(1000);     // 1 m vorwärts
}
