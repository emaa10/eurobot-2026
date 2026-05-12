#pragma once
#include <Arduino.h>

// Formatierte Ausgaben mit einheitlichem Präfix
inline void dbg_sep(const char *title) {
    Serial.println();
    Serial.println(F("┌──────────────────────────────────────────────┐"));
    Serial.printf ("│  TEST: %-38s│\n", title);
    Serial.println(F("└──────────────────────────────────────────────┘"));
}

inline void dbg_ok(const char *msg) {
    Serial.printf("  [OK]   %s\n", msg);
}

inline void dbg_fail(const char *msg) {
    Serial.printf("  [FAIL] %s\n", msg);
}

template<typename... Args>
inline void dbg_info(const char *fmt, Args... args) {
    Serial.printf("  [--]   ");
    Serial.printf(fmt, args...);
    Serial.println();
}
