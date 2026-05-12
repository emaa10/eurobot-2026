#pragma once

// ╔══════════════════════════════════════════════════════╗
// ║   SIMA TEST — Konfiguration                         ║
// ║   Hier Tests aktivieren/deaktivieren + Parameter    ║
// ╚══════════════════════════════════════════════════════╝

// ── Einzelne Tests ein-/ausschalten ──────────────────────
#define TEST_LED        1
#define TEST_PULLCORD   1
#define TEST_TOF        1
#define TEST_MOTORS     1
#define TEST_SERVO      1
#define TEST_STOPP      1   // ToF + Motor Stopp/Resume kombiniert

// ── Testparameter ─────────────────────────────────────────
#define MOTOR_TEST_CM      8    // Strecke je Richtung (cm)
#define MOTOR_TEST_DEG    90    // Winkel je Richtung  (°)
#define TOF_SAMPLES       15    // Messungen beim ToF-Test
#define SERVO_CYCLES       3    // Sweep-Zyklen beim Servo-Test
#define STOPP_TIMEOUT_MS 8000   // Max. Wartezeit Stopp-Test
