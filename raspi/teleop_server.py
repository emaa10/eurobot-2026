"""
Eurobot 2026 – Tele-Op-Server (Port 8000)

Steuerung des Roboters über WLAN: WASD am Laptop, Pfeiltasten / Touch-Buttons
am Handy. KeyDown startet die Fahrt (langer DD/TA-Befehl), KeyUp sendet `ST`
sofort an die ESP32, sodass der Motor abrupt stoppt.

Co-Existenz mit eurobot.service: der Server läuft immer mit, hält den ESP32-
Serial-Port aber NUR nach Druck auf „Activate“. Activate stoppt eurobot.service
temporär, Deactivate startet es wieder.
"""

import json
import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import serial
from flask import Flask, jsonify, request

# Default port, kann via env überschrieben werden
SERIAL_PORT = '/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'
BAUDRATE    = 115200
HTTP_PORT   = 8000

EUROBOT_UNIT = 'eurobot.service'

# Fahrt-Häppchen pro Refire: kurz genug, dass „release" innerhalb < 1 Häppchen
# zum Ziel führt, lang genug, dass der ESP nicht andauernd neue Cmds einfasst.
DRIVE_MM       = 50000     # 50 m je DD-Häppchen.  ST stoppt sofort,
                           # also keinen Grund kurze Chunks zu fahren –
                           # jeder Chunk-Wechsel ist ein sichtbarer Decel/
                           # Accel-Ramp in der Firmware.
TURN_DEG       = 7200      # 20 Umdrehungen je TA-Häppchen (selbe Logik)
HOLD_TIMEOUT_S = 1.0       # > 1.0 s kein Heartbeat → ST.  Heartbeat-Rate
                           # im Browser ist 100ms → ~10 pro Sekunde, damit
                           # WLAN-Aussetzer bis ~1s problemlos überbrückt
                           # werden ohne dass der Robot mitten in der Fahrt
                           # stoppt.

PIN_PULLCORD   = 22        # Pull-Up: LOW=Schnur drin, HIGH-Flanke=Start
RECORD_DIR     = Path('/home/eurobot/eurobot-2026/raspi/recordings')
RECORD_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger('teleop')


# ── ESP32-Wrapper ──────────────────────────────────────────────────────────
class ESPLink:
    """Hält die Serial-Verbindung zum ESP32 – nur aktiv, solange Tele-Op ‚activated‘ ist."""

    def __init__(self, port: str = SERIAL_PORT, baudrate: int = BAUDRATE):
        self.port = port
        self.baudrate = baudrate
        self.ser: serial.Serial | None = None
        self.lock = threading.Lock()
        self.last_state: str = 'unknown'
        self._rx_thread: threading.Thread | None = None
        self._rx_stop = threading.Event()

    @property
    def open(self) -> bool:
        return self.ser is not None

    def connect(self) -> bool:
        with self.lock:
            if self.ser is not None:
                return True
            try:
                self.ser = serial.Serial(self.port, self.baudrate, timeout=0.05)
                log.info(f"Serial geöffnet: {self.port}")
                time.sleep(0.3)  # ESP32 USB-Reset nach Port-Open
                self._write_raw_unlocked('ME')  # Motoren aktivieren
            except Exception as e:
                log.warning(f"Serial öffnen fehlgeschlagen: {e}")
                self.ser = None
                return False
        # RX-Drain-Thread starten
        self._rx_stop.clear()
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()
        return True

    def disconnect(self):
        with self.lock:
            if self.ser is None:
                return
            try:
                self._write_raw_unlocked('ST')   # sicherheitshalber stoppen
                time.sleep(0.05)
                self._write_raw_unlocked('MD')   # Motoren deaktivieren (Robot ist schiebbar)
                time.sleep(0.05)
            except Exception:
                pass
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
            log.info("Serial geschlossen")
        self._rx_stop.set()

    def _write_raw_unlocked(self, cmd: str):
        if self.ser is None:
            return
        try:
            self.ser.write(f"{cmd}\n".encode())
        except Exception as e:
            log.error(f"Serial write Fehler ({cmd}): {e}")
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def send(self, cmd: str) -> bool:
        with self.lock:
            if self.ser is None:
                return False
            log.info(f"→ ESP: {cmd}")
            self._write_raw_unlocked(cmd)
            return True

    def _rx_loop(self):
        while not self._rx_stop.is_set():
            ser = self.ser
            if ser is None:
                return
            try:
                line = ser.readline().decode(errors='ignore').strip()
                if line:
                    log.info(f"← ESP: {line}")
                    if line in ('OK', 'INTERRUPTED'):
                        self.last_state = line
                    # Auto-Refire bei vollendetem Häppchen (nur wenn definiert –
                    # vermeidet Forward-Reference während Modul-Import).
                    cb = globals().get('_refire_on_completion')
                    if cb:
                        cb(line)
            except Exception as e:
                log.warning(f"RX Fehler: {e}")
                return


esp = ESPLink()


# ── Greifer (STServos) ────────────────────────────────────────────────────
class GripperLink:
    """Hält Servos+Gripper-Wrapper. Lazy: erst nach activate() instanziiert,
    weil eurobot.service sonst den Servo-Port belegt. Bei jedem Disconnect
    wird der Port wieder geschlossen, damit main.py ihn nehmen kann."""

    def __init__(self):
        self.lock = threading.Lock()
        self.servos = None
        self.gripper = None

    @property
    def open(self) -> bool:
        return self.gripper is not None

    def connect(self) -> bool:
        with self.lock:
            if self.gripper is not None:
                return True
            try:
                # Lazy import: braucht serial-Port und STservo_sdk.
                from modules.servos import Servos
                from modules.gripper import Gripper
                self.servos = Servos()
                if not self.servos.available:
                    log.warning("Servos: Port nicht offen")
                    self.servos = None
                    return False
                self.gripper = Gripper(self.servos)
                log.info("Servos geöffnet")
                return True
            except Exception as e:
                log.warning(f"Gripper init fehlgeschlagen: {e}")
                self.servos = None
                self.gripper = None
                return False

    def disconnect(self):
        with self.lock:
            if self.servos is not None:
                try:
                    self.servos.detach_all()
                    self.servos.port_handler.closePort()
                except Exception:
                    pass
            self.servos = None
            self.gripper = None
            log.info("Servos geschlossen")

    def call(self, name: str) -> bool:
        """Führt eine Greifer-Aktion aus (siehe GRIPPER_ACTIONS)."""
        with self.lock:
            if self.gripper is None:
                return False
            fn = GRIPPER_ACTIONS.get(name)
            if fn is None:
                return False
            try:
                fn(self.gripper)
                return True
            except Exception as e:
                log.error(f"Gripper {name} Fehler: {e}")
                return False


# action-name → method-on-gripper
GRIPPER_ACTIONS = {
    'hg':  lambda g: g.home(),
    'gd':  lambda g: g.driving(),
    'gr':  lambda g: g.greifen(),
    'go':  lambda g: g.loslassen(),
    'gi':  lambda g: g.innen_greifen(),
    'ga':  lambda g: g.aussen_greifen(),
    'lh':  lambda g: g.lift_hoch(),
    'lr':  lambda g: g.lift_runter(),
    'w1h': lambda g: g.winker('r', True),
    'w1r': lambda g: g.winker('r', False),
    'w2h': lambda g: g.winker('l', True),
    'w2r': lambda g: g.winker('l', False),
}

gripper_link = GripperLink()


# ── eurobot.service Management ─────────────────────────────────────────────
def systemctl(action: str) -> tuple[bool, str]:
    """`sudo -n systemctl <action> eurobot.service` – braucht NOPASSWD."""
    try:
        r = subprocess.run(
            ['sudo', '-n', 'systemctl', action, EUROBOT_UNIT],
            capture_output=True, text=True, timeout=15,
        )
        ok = r.returncode == 0
        log.info(f"systemctl {action} {EUROBOT_UNIT} → rc={r.returncode}")
        return ok, (r.stderr or r.stdout).strip()
    except Exception as e:
        return False, str(e)


def eurobot_is_active() -> bool:
    r = subprocess.run(['systemctl', 'is-active', EUROBOT_UNIT],
                       capture_output=True, text=True)
    return r.stdout.strip() == 'active'


# ── Aktions-Mapping ────────────────────────────────────────────────────────
# Wir merken uns die zuletzt aktive Aktion, damit ein Tastenwechsel ohne
# zwischenliegendes KeyUp (z. B. W → A direkt) sauber via ST → neuer Befehl
# abgewickelt wird.
state = {
    'active':     None,    # aktuelle Fahrt-Aktion (None | forward | backward | left | right)
    'activated':  False,   # True wenn eurobot.service gestoppt und Serial offen
    'last_tick':  0.0,     # monotonic timestamp des letzten Heartbeat-Pings
    'last_seq':   0,       # höchste Session-Nummer, die wir gesehen haben
}
state_lock = threading.Lock()


ACTION_CMD = {
    'forward':  lambda: f'DD{DRIVE_MM}',
    'backward': lambda: f'DD-{DRIVE_MM}',
    'left':     lambda: f'TA-{TURN_DEG}',
    'right':    lambda: f'TA{TURN_DEG}',
}

# Kreis-Mode: laeuft endlos auf der ESP, kein Refire / Watchdog noetig
circle_state = {'running': False}


def hard_stop():
    """ESP-Firmware: `MOVING + ST → PAUSED`, NICHT IDLE. Damit der nächste
    DD/TA aus der Queue auch verarbeitet wird, müssen wir doppelt stoppen:
    1. ST → MOVING→PAUSED (Motor steht)
    2. ST → PAUSED→IDLE   (INTERRUPTED, bereit für neues Cmd)"""
    esp.send('ST')
    time.sleep(0.03)
    esp.send('ST')
    time.sleep(0.02)


def do_action(action: str, seq: int = 0) -> tuple[bool, str]:
    """Heartbeat-Endpoint: startet die Aktion beim ersten Aufruf, refresht
    danach nur den `last_tick`-Timer, solange dieselbe Taste gehalten wird.

    `seq` ist eine Session-Nummer vom Client – Requests mit kleinerem Seq
    sind verspätete Heartbeats und werden verworfen (sonst kann ein stale
    Heartbeat eine schon gestoppte Aktion wiederbeleben)."""
    with state_lock:
        if not state['activated']:
            return False, 'not activated'

        # Stale-Request-Filter (Heartbeat aus alter Session überholt Stop / neue Action)
        if seq and seq < state['last_seq']:
            return False, f'stale (seq {seq} < {state["last_seq"]})'
        if seq:
            state['last_seq'] = seq

        if action == 'stop':
            if state['active'] is not None or circle_state['running']:
                hard_stop()
                rec_log_event('drive', 'stop')
            state['active'] = None
            circle_state['running'] = False
            return True, 'ok'

        if action not in ACTION_CMD:
            return False, f'unknown action: {action}'

        # Heartbeat: Aktion läuft schon → nur Timer aktualisieren
        if state['active'] == action:
            state['last_tick'] = time.monotonic()
            return True, 'tick'

        # Wechsel: erst sauber stoppen (ST,ST), damit ESP in IDLE ist,
        # bevor das neue DD/TA in die Queue geht.
        if state['active'] is not None or circle_state['running']:
            hard_stop()
            circle_state['running'] = False

        esp.send(ACTION_CMD[action]())
        state['active']    = action
        state['last_tick'] = time.monotonic()
        rec_log_event('drive', action)
        return True, 'start'


def circle_start() -> tuple[bool, str]:
    """Startet den hardcodeten Kreis-Mode auf der ESP (CC-Befehl)."""
    with state_lock:
        if not state['activated']:
            return False, 'not activated'
        if circle_state['running']:
            return True, 'already running'
        # Falls noch eine Fahrt-Aktion laeuft: erst sauber stoppen
        if state['active'] is not None:
            hard_stop()
            state['active'] = None
        esp.send('CC')
        circle_state['running'] = True
    rec_log_event('drive', 'circle_start')
    return True, 'ok'


def circle_stop() -> tuple[bool, str]:
    """Stoppt den Kreis-Mode (ST,ST damit ESP wieder im IDLE landet)."""
    with state_lock:
        if not circle_state['running']:
            return True, 'not running'
        hard_stop()
        circle_state['running'] = False
    rec_log_event('drive', 'circle_stop')
    return True, 'ok'


def do_gripper(action: str) -> tuple[bool, str]:
    """Greifer-Aktion (single shot). Auch im recording-Log."""
    if not state['activated']:
        return False, 'not activated'
    if action not in GRIPPER_ACTIONS:
        return False, f'unknown gripper action: {action}'
    if not gripper_link.open:
        return False, 'servos nicht verfügbar'
    ok = gripper_link.call(action)
    if ok:
        rec_log_event('gripper', action)
    return ok, 'ok' if ok else 'fail'


def _watchdog_loop():
    """Stoppt die Fahrt automatisch, wenn der Browser >HOLD_TIMEOUT_S keinen
    Heartbeat schickt (Tab zu, Netzwerk weg, keyup verschluckt, …)."""
    while True:
        time.sleep(0.05)
        with state_lock:
            if state['active'] is None:
                continue
            if time.monotonic() - state['last_tick'] > HOLD_TIMEOUT_S:
                log.info(f"Watchdog: {state['active']} → ST (kein Heartbeat)")
                hard_stop()
                state['active'] = None


def _refire_on_completion(line: str):
    """ESP meldet `OK` (Häppchen fertig) → wenn Taste noch gehalten, sofort
    nochmal dasselbe Cmd schicken: nahtloses Weiterfahren."""
    if line != 'OK':
        return
    with state_lock:
        if state['active'] is None or not state['activated']:
            return
        if time.monotonic() - state['last_tick'] > HOLD_TIMEOUT_S:
            return
        esp.send(ACTION_CMD[state['active']]())


threading.Thread(target=_watchdog_loop, daemon=True).start()


def activate() -> tuple[bool, str]:
    """eurobot.service stoppen → ESP-Serial + Servos öffnen → Tele-Op bereit."""
    with state_lock:
        if state['activated']:
            return True, 'already activated'

        log.info("ACTIVATE: stopping eurobot.service …")
        ok, msg = systemctl('stop')
        if not ok:
            return False, f'systemctl stop failed: {msg}'

        # Kurz warten bis main.py die Ports wirklich freigegeben hat
        esp_ok = False
        for _ in range(20):
            time.sleep(0.1)
            if esp.connect():
                esp_ok = True
                break
        if not esp_ok:
            systemctl('start')
            return False, 'ESP-Serial-Port nicht verfügbar'

        # Servos sind „nice to have" – kein Fail, wenn sie nicht aufgehen
        gripper_link.connect()

        state['activated'] = True
        state['active']    = None
        state['last_seq']  = 0     # frische Session – stale-Filter resetten
        log.info(f"ACTIVATE: ok (gripper={'on' if gripper_link.open else 'off'})")
        return True, 'ok'


def deactivate() -> tuple[bool, str]:
    """Serial schließen → eurobot.service wieder starten."""
    with state_lock:
        if not state['activated']:
            return True, 'not activated'
        log.info("DEACTIVATE: closing serial, starting eurobot.service …")
        esp.disconnect()
        gripper_link.disconnect()
        state['active']    = None
        state['activated'] = False
    ok, msg = systemctl('start')
    return ok, msg or 'ok'


# ── Recording-Engine ───────────────────────────────────────────────────────
# Wir loggen *high-level* Events: jeden Aktionswechsel (forward/back/left/right/
# stop) sowie Greifer-Calls. Heartbeats werden nicht geloggt – beim Playback
# halten wir die Aktion automatisch über die nächste Aktion oder via Wartezeit.
rec_lock = threading.Lock()
rec_state = {
    'recording': False,        # True während Aufnahme
    'events':    [],           # list[ {t, kind, action} ]
    'start':     0.0,
    'playing':   False,        # True während Playback
    'play_name': None,
    'armed':     None,         # Name des Recordings, das per Pull-Cord triggert
}


def rec_log_event(kind: str, action: str):
    """Aus do_action / do_gripper aufgerufen – nur wenn recording aktiv."""
    with rec_lock:
        if not rec_state['recording']:
            return
        rec_state['events'].append({
            't': round(time.monotonic() - rec_state['start'], 3),
            'kind': kind,        # 'drive' | 'gripper'
            'action': action,
        })


def rec_start():
    with rec_lock:
        rec_state['recording'] = True
        rec_state['events']    = []
        rec_state['start']     = time.monotonic()
    log.info("Recording: START")


def rec_stop() -> list[dict]:
    with rec_lock:
        rec_state['recording'] = False
        evts = list(rec_state['events'])
    log.info(f"Recording: STOP ({len(evts)} events)")
    return evts


_SAFE_NAME = re.compile(r'^[A-Za-z0-9 _\-äöüÄÖÜß]{1,40}$')


def rec_save(name: str, events: list[dict]) -> tuple[bool, str]:
    if not _SAFE_NAME.match(name):
        return False, 'Name ungültig (Buchstaben/Zahlen/Leerzeichen, max 40)'
    path = RECORD_DIR / f"{name}.json"
    try:
        with open(path, 'w') as f:
            json.dump({'name': name, 'events': events,
                       'created': time.time()}, f, indent=2)
    except Exception as e:
        return False, str(e)
    log.info(f"Recording '{name}' gespeichert ({len(events)} Events)")
    return True, 'ok'


def rec_list() -> list[dict]:
    out = []
    for p in sorted(RECORD_DIR.glob('*.json')):
        try:
            with open(p) as f:
                data = json.load(f)
            evts = data.get('events', [])
            dur  = evts[-1]['t'] if evts else 0
            out.append({'name': data.get('name', p.stem),
                        'events': len(evts), 'duration': dur})
        except Exception:
            pass
    return out


def rec_load(name: str) -> list[dict] | None:
    path = RECORD_DIR / f"{name}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f).get('events', [])


def rec_delete(name: str) -> bool:
    path = RECORD_DIR / f"{name}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def _playback_thread(name: str, events: list[dict]):
    """Spielt eine Event-Sequenz mit Originaltiming ab."""
    log.info(f"Playback START: '{name}' ({len(events)} Events)")
    t0 = time.monotonic()
    try:
        for ev in events:
            target = t0 + ev['t']
            while True:
                now = time.monotonic()
                if not rec_state['playing']:
                    log.info("Playback abgebrochen")
                    hard_stop()
                    return
                if now >= target:
                    break
                time.sleep(min(0.02, target - now))

            kind, action = ev['kind'], ev['action']
            if kind == 'drive':
                # do_action mit „immer frischer" seq
                do_action(action, seq=int(time.time() * 1000))
            elif kind == 'gripper':
                gripper_link.call(action)
        # Am Ende sicherheitshalber stoppen
        hard_stop()
    finally:
        with rec_lock:
            rec_state['playing']   = False
            rec_state['play_name'] = None
        log.info(f"Playback END: '{name}'")


def rec_play(name: str) -> tuple[bool, str]:
    if rec_state['playing']:
        return False, 'schon ein Playback aktiv'
    if not state['activated']:
        return False, 'erst Activate drücken'
    events = rec_load(name)
    if events is None:
        return False, 'unbekannt'
    with rec_lock:
        rec_state['playing']   = True
        rec_state['play_name'] = name
    threading.Thread(target=_playback_thread, args=(name, events),
                     daemon=True).start()
    return True, 'ok'


def rec_play_stop() -> tuple[bool, str]:
    with rec_lock:
        if not rec_state['playing']:
            return True, 'kein Playback aktiv'
        rec_state['playing'] = False
    return True, 'ok'


# ── Pull-Cord-Watcher ──────────────────────────────────────────────────────
_pullcord_setup = False
_pullcord_last_high = False


def _pullcord_init():
    """Lazy GPIO-Setup – nur wenn der erste Arm-Request kommt, damit wir
    main.py beim Boot nicht mit konkurrierendem GPIO-Init stören."""
    global _pullcord_setup
    if _pullcord_setup:
        return
    try:
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_PULLCORD, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        _pullcord_setup = True
        log.info(f"Pull-Cord GPIO {PIN_PULLCORD} initialisiert")
    except Exception as e:
        log.warning(f"Pull-Cord init Fehler: {e}")


def _pullcord_loop():
    """Polling-Loop: bei LOW→HIGH-Flanke (Schnur gezogen) das gearmte
    Recording starten. Activate wird bei Bedarf automatisch ausgelöst."""
    global _pullcord_last_high
    while True:
        time.sleep(0.05)
        armed = rec_state['armed']
        if not armed or not _pullcord_setup:
            _pullcord_last_high = False
            continue
        try:
            import RPi.GPIO as GPIO
            high = GPIO.input(PIN_PULLCORD) == GPIO.HIGH
        except Exception:
            continue
        if high and not _pullcord_last_high:
            log.info(f"Pull-Cord HIGH-Flanke → Playback '{armed}'")
            if not state['activated']:
                ok, msg = activate()
                if not ok:
                    log.error(f"Auto-Activate fehlgeschlagen: {msg}")
                    _pullcord_last_high = high
                    continue
            rec_play(armed)
            with rec_lock:
                rec_state['armed'] = None    # nur 1× pro Arm-Druck
        _pullcord_last_high = high


threading.Thread(target=_pullcord_loop, daemon=True).start()


# ── HTML-UI ────────────────────────────────────────────────────────────────
INDEX_HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#0b0f1a">
<title>Eurobot Tele-Op</title>
<style>
  :root {
    color-scheme: dark;
    --bg-1:    #0b0f1a;
    --bg-2:    #131a2c;
    --card:    rgba(255,255,255,0.04);
    --border:  rgba(255,255,255,0.08);
    --accent:  #3b82f6;
    --accent2: #06b6d4;
    --danger:  #ef4444;
    --ok:      #22c55e;
    --text:    #e5e7eb;
    --muted:   #9ca3af;
    --pad: clamp(76px, 22vw, 110px);
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { margin: 0; padding: 0; min-height: 100%; }
  body {
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
    color: var(--text);
    background:
      radial-gradient(1200px 600px at 80% -10%, rgba(59,130,246,0.18), transparent 60%),
      radial-gradient(900px 500px at -10% 110%, rgba(6,182,212,0.16), transparent 55%),
      linear-gradient(180deg, var(--bg-1), var(--bg-2));
    background-attachment: fixed;
    min-height: 100dvh;
    display: flex; flex-direction: column; align-items: center;
    gap: 18px; padding: 18px max(14px, env(safe-area-inset-right))
                    max(20px, env(safe-area-inset-bottom))
                    max(14px, env(safe-area-inset-left));
    overscroll-behavior: none; touch-action: manipulation;
    user-select: none; -webkit-user-select: none;
  }

  /* ── Header ─────────────────────────────────────────────── */
  header {
    width: 100%; max-width: 480px;
    display: flex; align-items: center; justify-content: space-between;
  }
  .brand { display: flex; align-items: center; gap: 10px; }
  .logo {
    width: 36px; height: 36px; border-radius: 10px;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    display: grid; place-items: center; font-size: 20px;
    box-shadow: 0 6px 24px rgba(59,130,246,0.4);
  }
  h1 { margin: 0; font-size: 17px; font-weight: 700; letter-spacing: 0.3px; }
  .sub { font-size: 11px; color: var(--muted); letter-spacing: 0.5px; text-transform: uppercase; }

  .link-pill {
    display: flex; align-items: center; gap: 6px;
    background: var(--card); border: 1px solid var(--border);
    padding: 6px 10px; border-radius: 999px;
    font-size: 12px; font-family: ui-monospace, 'JetBrains Mono', monospace;
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ok);
         box-shadow: 0 0 12px var(--ok); transition: background 0.2s, box-shadow 0.2s; }
  .dot.err { background: var(--danger); box-shadow: 0 0 12px var(--danger); }

  /* ── Status-Karte ───────────────────────────────────────── */
  .status {
    width: 100%; max-width: 480px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: 16px; padding: 14px 18px;
    backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
    display: flex; align-items: center; justify-content: space-between;
  }
  .status .lbl { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.6px; }
  .status .val { font-size: 18px; font-weight: 700; font-family: ui-monospace, monospace; }
  .status .val.idle { color: var(--muted); }
  .status .val.go   { color: var(--accent2); text-shadow: 0 0 18px rgba(6,182,212,0.5); }

  /* ── D-Pad ──────────────────────────────────────────────── */
  .pad {
    display: grid;
    grid-template-columns: repeat(3, var(--pad));
    grid-template-rows:    repeat(3, var(--pad));
    gap: 12px;
    padding: 18px;
    border-radius: 28px;
    background: var(--card);
    border: 1px solid var(--border);
    box-shadow: 0 10px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04);
    backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  }
  .btn {
    position: relative;
    background: linear-gradient(180deg, #1e293b, #0f172a);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    color: var(--text);
    font-size: clamp(28px, 8vw, 40px);
    font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    transition: transform 80ms ease, box-shadow 120ms ease, background 120ms ease;
    box-shadow: 0 4px 14px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.05);
  }
  .btn:hover { background: linear-gradient(180deg, #243044, #131c30); }
  .btn:active, .btn.active {
    background: linear-gradient(180deg, var(--accent), #1d4ed8);
    border-color: rgba(255,255,255,0.18);
    transform: scale(0.94);
    box-shadow: 0 0 0 4px rgba(59,130,246,0.18), 0 8px 24px rgba(59,130,246,0.45);
  }
  .btn.stop {
    background: linear-gradient(180deg, #7f1d1d, #450a0a);
    font-size: clamp(14px, 4vw, 17px);
    letter-spacing: 1px;
  }
  .btn.stop:active, .btn.stop.active {
    background: linear-gradient(180deg, var(--danger), #991b1b);
    box-shadow: 0 0 0 4px rgba(239,68,68,0.22), 0 8px 24px rgba(239,68,68,0.5);
  }
  .empty { visibility: hidden; }

  /* ── Activate-Toggle ────────────────────────────────────── */
  .toggle {
    width: 100%; max-width: 480px;
    background: linear-gradient(180deg, #166534, #14532d);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px; color: white;
    padding: 16px 18px; font-size: 16px; font-weight: 700;
    cursor: pointer; letter-spacing: 0.8px;
    transition: background 150ms ease, transform 100ms ease, box-shadow 150ms ease;
    box-shadow: 0 8px 24px rgba(34,197,94,0.3), inset 0 1px 0 rgba(255,255,255,0.08);
  }
  .toggle:hover { transform: translateY(-1px); }
  .toggle:active { transform: translateY(1px); }
  .toggle[data-state="on"] {
    background: linear-gradient(180deg, #b91c1c, #7f1d1d);
    box-shadow: 0 8px 24px rgba(239,68,68,0.35), inset 0 1px 0 rgba(255,255,255,0.08);
  }
  .toggle[data-state="busy"] {
    background: linear-gradient(180deg, #475569, #1e293b);
    cursor: wait; box-shadow: none;
  }

  /* Tele-Op-Pad deaktivieren, solange nicht activated */
  body:not(.activated) .pad,
  body:not(.activated) .grip,
  body:not(.activated) .rec-controls { opacity: 0.4; pointer-events: none; filter: grayscale(0.4); }

  /* ── Greifer-Buttons ───────────────────────────────────── */
  .panel {
    width: 100%; max-width: 480px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: 18px; padding: 16px;
    backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
    display: flex; flex-direction: column; gap: 12px;
  }
  .panel h3 {
    margin: 0; font-size: 11px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 1px; font-weight: 700;
    display: flex; align-items: center; gap: 8px;
  }
  .grip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .gbtn {
    background: linear-gradient(180deg, #1e293b, #0f172a);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px; color: var(--text);
    padding: 12px 6px; font-size: 12px; font-weight: 600;
    cursor: pointer; line-height: 1.1;
    transition: background 100ms, transform 80ms;
  }
  .gbtn:hover  { background: linear-gradient(180deg, #243044, #131c30); }
  .gbtn:active { background: linear-gradient(180deg, var(--accent), #1d4ed8);
                 transform: scale(0.95); }
  .gbtn .ico  { display: block; font-size: 20px; margin-bottom: 2px; }

  /* ── Recording ─────────────────────────────────────────── */
  .rec-controls { display: flex; gap: 8px; flex-wrap: wrap; }
  .rec-btn {
    background: linear-gradient(180deg, #1e293b, #0f172a);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px; color: var(--text);
    padding: 10px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
    flex: 1; min-width: 100px;
  }
  .rec-btn:hover  { background: linear-gradient(180deg, #243044, #131c30); }
  .rec-btn:active { transform: scale(0.97); }
  .rec-btn.recording {
    background: linear-gradient(180deg, #dc2626, #7f1d1d);
    box-shadow: 0 0 0 4px rgba(239,68,68,0.18);
    animation: pulse 1.4s ease-in-out infinite;
  }
  @keyframes pulse { 50% { box-shadow: 0 0 0 8px rgba(239,68,68,0.05); } }

  .name-input {
    flex: 2; min-width: 140px;
    background: rgba(0,0,0,0.3); border: 1px solid var(--border);
    border-radius: 10px; color: var(--text);
    padding: 10px 12px; font-size: 13px;
    font-family: inherit;
  }
  .name-input:focus { outline: 2px solid var(--accent); border-color: var(--accent); }

  .rec-list { display: flex; flex-direction: column; gap: 6px; max-height: 240px; overflow-y: auto; }
  .rec-item {
    display: flex; align-items: center; gap: 6px;
    background: rgba(0,0,0,0.2); border: 1px solid var(--border);
    border-radius: 10px; padding: 8px 10px; font-size: 13px;
  }
  .rec-item .name { flex: 1; font-weight: 600; }
  .rec-item .meta { font-size: 11px; color: var(--muted); font-family: ui-monospace, monospace; }
  .rec-item button {
    background: transparent; border: 1px solid var(--border);
    border-radius: 8px; color: var(--text);
    padding: 5px 9px; font-size: 12px; cursor: pointer;
  }
  .rec-item button:hover  { background: rgba(255,255,255,0.06); }
  .rec-item .play:hover   { background: var(--ok); border-color: var(--ok); color: white; }
  .rec-item .arm:hover    { background: #f59e0b; border-color: #f59e0b; color: black; }
  .rec-item .arm.armed    { background: #f59e0b; border-color: #f59e0b; color: black;
                            box-shadow: 0 0 0 3px rgba(245,158,11,0.18); }
  .rec-item .del:hover    { background: var(--danger); border-color: var(--danger); color: white; }

  .empty-list { text-align: center; padding: 14px; color: var(--muted); font-size: 13px; font-style: italic; }

  .arm-banner {
    margin-top: 6px; padding: 10px 12px;
    background: linear-gradient(90deg, rgba(245,158,11,0.18), rgba(245,158,11,0.06));
    border: 1px solid rgba(245,158,11,0.45);
    border-radius: 10px; font-size: 13px; color: #fbbf24;
    display: none;
  }
  .arm-banner.on { display: block; }

  .hint {
    font-size: 12px; color: var(--muted); text-align: center;
    max-width: 480px; line-height: 1.5;
  }
  kbd {
    background: var(--card); border: 1px solid var(--border);
    border-bottom-width: 2px; padding: 2px 6px; border-radius: 5px;
    font-family: ui-monospace, monospace; font-size: 11px; color: var(--text);
  }
</style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo">🤖</div>
      <div>
        <h1>Eurobot Tele-Op</h1>
        <div class="sub">2026 · live control</div>
      </div>
    </div>
    <div class="link-pill"><span class="dot" id="dot"></span><span id="link">online</span></div>
  </header>

  <div class="status">
    <div>
      <div class="lbl">Modus</div>
      <div class="val idle" id="mode">eurobot.service</div>
    </div>
    <div style="text-align:right;">
      <div class="lbl">Aktion</div>
      <div class="val idle" id="active">idle</div>
    </div>
  </div>

  <button class="toggle" id="toggle" data-state="off">▶ ACTIVATE TELE-OP</button>

  <div class="pad" id="pad">
    <div class="empty"></div>
    <div class="btn" data-action="forward">▲</div>
    <div class="empty"></div>

    <div class="btn" data-action="left">◀</div>
    <div class="btn stop" data-action="stop">STOP</div>
    <div class="btn" data-action="right">▶</div>

    <div class="empty"></div>
    <div class="btn" data-action="backward">▼</div>
    <div class="empty"></div>
  </div>

  <div class="panel">
    <h3>🌀 Kreis-Modus
      <span id="circle-state" style="margin-left:auto;font-family:ui-monospace,monospace;color:var(--muted);text-transform:none;letter-spacing:0;">idle</span>
    </h3>
    <div class="rec-controls">
      <button class="rec-btn" id="circle-start">▶ Kreis Start</button>
      <button class="rec-btn" id="circle-stop">■ Kreis Stop</button>
    </div>
  </div>

  <div class="panel">
    <h3>🦾 Greifer</h3>
    <div class="grip">
      <button class="gbtn" data-grip="hg"><span class="ico">🏠</span>Home</button>
      <button class="gbtn" data-grip="gd"><span class="ico">🚗</span>Driving</button>
      <button class="gbtn" data-grip="gr"><span class="ico">🤏</span>Greifen</button>
      <button class="gbtn" data-grip="go"><span class="ico">👐</span>Auf</button>

      <button class="gbtn" data-grip="lh"><span class="ico">⬆️</span>Lift ↑</button>
      <button class="gbtn" data-grip="lr"><span class="ico">⬇️</span>Lift ↓</button>
      <button class="gbtn" data-grip="gi"><span class="ico">🔘</span>Innen</button>
      <button class="gbtn" data-grip="ga"><span class="ico">⚪</span>Außen</button>

      <button class="gbtn" data-grip="w1h"><span class="ico">↗️</span>W1 ↑</button>
      <button class="gbtn" data-grip="w1r"><span class="ico">↘️</span>W1 ↓</button>
      <button class="gbtn" data-grip="w2h"><span class="ico">↖️</span>W2 ↑</button>
      <button class="gbtn" data-grip="w2r"><span class="ico">↙️</span>W2 ↓</button>
    </div>
  </div>

  <div class="panel">
    <h3>🎬 Recording <span id="rec-state" style="margin-left:auto;font-family:ui-monospace,monospace;color:var(--muted);text-transform:none;letter-spacing:0;">idle</span></h3>
    <div class="rec-controls">
      <button class="rec-btn" id="rec-toggle">● Record</button>
      <input class="name-input" id="rec-name" placeholder="Name z.B. taktik1" maxlength="40">
      <button class="rec-btn" id="rec-save">💾 Save</button>
    </div>
    <div class="rec-list" id="rec-list"></div>
    <div class="arm-banner" id="arm-banner">🎯 Pull-Cord scharf — gezogen → Playback startet</div>
  </div>

  <div class="hint">
    💻 <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> oder Pfeiltasten · Taste loslassen = Stop ·
    <kbd>Space</kbd> = Not-Stop · 📱 Tippen &amp; halten<br>
    <kbd>Enter</kbd> Activate / Deactivate · 🎯 Arm = ein Recording startet, sobald die Pull-Schnur HIGH geht
  </div>

<script>
const $ = id => document.getElementById(id);
const activeEl = $('active');
const modeEl   = $('mode');
const linkEl   = $('link');
const dotEl    = $('dot');
const toggleEl = $('toggle');

let activeAction = null;
let activated    = false;
// Statt eines Zählers nutzen wir Date.now() – damit ist die Sequenz auch nach
// Reload, Tab-Wechsel oder Server-Restart immer monoton steigend.
function nextSeq(){ return Date.now(); }
const LABELS = { forward:'▲ forward', backward:'▼ backward', left:'◀ left', right:'▶ right' };

async function send(action, seq){
  if (!activated) return;                       // ohne Activate keine Steuerung
  try {
    const r = await fetch('/cmd/' + action + '?s=' + seq, { method: 'POST' });
    if (!r.ok && r.status !== 409) throw new Error(r.status);
    linkEl.textContent = 'online'; dotEl.classList.remove('err');
  } catch (e){
    linkEl.textContent = 'offline'; dotEl.classList.add('err');
  }
}

function applyActivated(on){
  activated = on;
  document.body.classList.toggle('activated', on);
  toggleEl.dataset.state = on ? 'on' : 'off';
  toggleEl.textContent   = on ? '■ DEACTIVATE TELE-OP' : '▶ ACTIVATE TELE-OP';
  modeEl.textContent     = on ? 'tele-op' : 'eurobot.service';
  modeEl.classList.toggle('go',   on);
  modeEl.classList.toggle('idle', !on);
  if (!on) { activeAction = null; activeEl.textContent = 'idle';
             activeEl.classList.remove('go'); activeEl.classList.add('idle');
             setActiveBtn(null); }
}

async function toggleActivate(){
  if (toggleEl.dataset.state === 'busy') return;
  const want = !activated;
  toggleEl.dataset.state = 'busy';
  toggleEl.textContent   = want ? '… stopping eurobot …' : '… starting eurobot …';
  try {
    const r = await fetch(want ? '/activate' : '/deactivate', { method: 'POST' });
    const j = await r.json();
    if (!j.ok) throw new Error(j.message || 'failed');
    applyActivated(want);
    if (navigator.vibrate) navigator.vibrate(want ? [30,40,30] : 25);
  } catch (e){
    applyActivated(activated);                  // alten Zustand restaurieren
    alert('Fehler: ' + e.message);
  }
}

let holdTimer = null;
const HEARTBEAT_MS = 100;

function start(action){
  if (!activated || action === activeAction) return;
  activeAction = action;
  activeEl.textContent = LABELS[action] || action;
  activeEl.classList.remove('idle'); activeEl.classList.add('go');
  setActiveBtn(action);
  if (navigator.vibrate) navigator.vibrate(15);
  send(action, nextSeq());                           // initialer Trigger
  if (holdTimer) clearInterval(holdTimer);
  holdTimer = setInterval(() => {                    // Heartbeat
    if (activeAction === action) send(action, nextSeq());
    else { clearInterval(holdTimer); holdTimer = null; }
  }, HEARTBEAT_MS);
}

function stop(){
  if (holdTimer) { clearInterval(holdTimer); holdTimer = null; }
  if (activeAction === null) return;
  activeAction = null;
  activeEl.textContent = 'idle';
  activeEl.classList.remove('go'); activeEl.classList.add('idle');
  setActiveBtn(null);
  if (navigator.vibrate) navigator.vibrate(8);
  send('stop', nextSeq());
}

function setActiveBtn(action){
  document.querySelectorAll('.btn').forEach(b => {
    b.classList.toggle('active', b.dataset.action === action);
  });
}

// ── Keyboard ─────────────────────────────────────────────────────────────
const KEYMAP = {
  'w':'forward', 'W':'forward', 'ArrowUp':'forward',
  's':'backward','S':'backward','ArrowDown':'backward',
  'a':'left',    'A':'left',    'ArrowLeft':'left',
  'd':'right',   'D':'right',   'ArrowRight':'right',
};

window.addEventListener('keydown', e => {
  if (e.repeat) return;                          // Browser-Repeat ignorieren
  if (e.key === ' ') { e.preventDefault(); stop(); return; }
  if (e.key === 'Enter') { e.preventDefault(); toggleActivate(); return; }
  const a = KEYMAP[e.key];
  if (a){ e.preventDefault(); start(a); }
});
window.addEventListener('keyup', e => {
  const a = KEYMAP[e.key];
  if (a){ e.preventDefault(); if (activeAction === a) stop(); }
});
window.addEventListener('blur', stop);           // Fenster verliert Fokus → Stop

// ── Touch / Mouse auf den Buttons ────────────────────────────────────────
document.querySelectorAll('.btn').forEach(btn => {
  const a = btn.dataset.action;
  const down = e => { e.preventDefault();
    if (a === 'stop') stop(); else start(a);
  };
  const up = e => { e.preventDefault();
    if (a !== 'stop') stop();
  };
  btn.addEventListener('pointerdown',  down);
  btn.addEventListener('pointerup',    up);
  btn.addEventListener('pointercancel',up);
  btn.addEventListener('pointerleave', up);
});

toggleEl.addEventListener('click', toggleActivate);

// ── Greifer ────────────────────────────────────────────────────────────
document.querySelectorAll('.gbtn').forEach(b => {
  b.addEventListener('click', async () => {
    const a = b.dataset.grip;
    if (!activated) return;
    if (navigator.vibrate) navigator.vibrate(8);
    try {
      const r = await fetch('/gripper/' + a, { method: 'POST' });
      if (!r.ok){ const j = await r.json(); alert('Greifer: ' + (j.message||r.status)); }
    } catch(e){ alert('Greifer: ' + e.message); }
  });
});

// ── Kreis-Mode ─────────────────────────────────────────────────────────
const circleStartBtn = $('circle-start');
const circleStopBtn  = $('circle-stop');
const circleStateEl  = $('circle-state');
let circleRunning = false;

function applyCircleState(on){
  circleRunning = on;
  circleStateEl.textContent = on ? 'fährt…' : 'idle';
  circleStartBtn.classList.toggle('recording', on);
}

circleStartBtn.addEventListener('click', async () => {
  if (!activated){ alert('Erst ▶ ACTIVATE drücken'); return; }
  try {
    const r = await fetch('/circle/start', { method:'POST' });
    const j = await r.json();
    if (!j.ok){ alert('Kreis: ' + (j.message||r.status)); return; }
    applyCircleState(true);
  } catch(e){ alert('Kreis: ' + e.message); }
});

circleStopBtn.addEventListener('click', async () => {
  try {
    const r = await fetch('/circle/stop', { method:'POST' });
    const j = await r.json();
    applyCircleState(false);
    if (!j.ok){ alert('Kreis stop: ' + (j.message||r.status)); }
  } catch(e){ alert('Kreis: ' + e.message); }
});

// ── Recording ──────────────────────────────────────────────────────────
const recToggle = $('rec-toggle');
const recState  = $('rec-state');
const recName   = $('rec-name');
const recSave   = $('rec-save');
const recList   = $('rec-list');
const armBanner = $('arm-banner');
let recording = false, playing = false, armedName = null;

async function pollStatus(){
  try {
    const r = await fetch('/record/list');
    const j = await r.json();
    recording = j.recording; playing = j.playing; armedName = j.armed;
    recToggle.textContent = recording ? '■ Stop Recording' : '● Record';
    recToggle.classList.toggle('recording', recording);
    recState.textContent = playing ? 'PLAYING: ' + j.play_name
                          : recording ? 'recording…' : 'idle';
    armBanner.classList.toggle('on', !!armedName);
    if (armedName) armBanner.textContent = `🎯 Pull-Cord scharf für „${armedName}" – ziehen startet Playback`;
    renderList(j.recordings);
  } catch(e){}
  // Kreis-Status pollen (separater Endpoint /status)
  try {
    const r2 = await fetch('/status');
    const j2 = await r2.json();
    applyCircleState(!!j2.circle);
  } catch(e){}
}
setInterval(pollStatus, 1500);
pollStatus();

function renderList(recs){
  if (!recs.length){
    recList.innerHTML = '<div class="empty-list">noch keine Recordings — drück ● Record, fahr was, dann 💾 Save</div>';
    return;
  }
  recList.innerHTML = recs.map(r => `
    <div class="rec-item">
      <div>
        <div class="name">${escapeHtml(r.name)}</div>
        <div class="meta">${r.events} ev · ${r.duration.toFixed(1)}s</div>
      </div>
      <button class="play" data-act="play" data-name="${escapeHtml(r.name)}">▶</button>
      <button class="arm ${armedName===r.name?'armed':''}" data-act="arm" data-name="${escapeHtml(r.name)}">🎯</button>
      <button class="del"  data-act="del"  data-name="${escapeHtml(r.name)}">🗑</button>
    </div>`).join('');
}

function escapeHtml(s){ return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

recList.addEventListener('click', async e => {
  const btn = e.target.closest('button');
  if (!btn) return;
  const name = btn.dataset.name, act = btn.dataset.act;
  if (act === 'play'){
    const r = await fetch('/record/play/' + encodeURIComponent(name), { method:'POST' });
    const j = await r.json();
    if (!j.ok) alert(j.message);
  } else if (act === 'arm'){
    const target = (armedName === name) ? '' : name;     // toggle
    await fetch('/record/arm?name=' + encodeURIComponent(target), { method:'POST' });
  } else if (act === 'del'){
    if (!confirm(`„${name}" wirklich löschen?`)) return;
    await fetch('/record/delete/' + encodeURIComponent(name), { method:'POST' });
  }
  pollStatus();
});

recToggle.addEventListener('click', async () => {
  if (!activated){ alert('Erst ▶ ACTIVATE drücken'); return; }
  if (!recording){
    await fetch('/record/start', { method:'POST' });
  } else {
    await fetch('/record/stop',  { method:'POST' });
  }
  pollStatus();
});

recSave.addEventListener('click', async () => {
  const name = recName.value.trim();
  if (!name){ alert('Name eingeben'); return; }
  const r = await fetch('/record/save?name=' + encodeURIComponent(name), { method:'POST' });
  const j = await r.json();
  if (!j.ok){ alert(j.message); return; }
  recName.value = '';
  pollStatus();
});

// Initialer Status (Activate-Toggle)
fetch('/status').then(r => r.json()).then(j => applyActivated(!!j.activated))
  .catch(() => applyActivated(false));
</script>
</body>
</html>
"""


# ── Flask-App ──────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.get('/')
def index():
    return INDEX_HTML


@app.post('/cmd/<action>')
def cmd(action):
    try:
        seq = int(request.args.get('s', 0))
    except ValueError:
        seq = 0
    ok, msg = do_action(action, seq)
    code = 200 if ok else 409
    return jsonify(ok=ok, message=msg, active=state['active']), code


@app.post('/activate')
def http_activate():
    ok, msg = activate()
    return jsonify(ok=ok, message=msg, activated=state['activated']), (200 if ok else 500)


@app.post('/deactivate')
def http_deactivate():
    ok, msg = deactivate()
    return jsonify(ok=ok, message=msg, activated=state['activated']), (200 if ok else 500)


@app.post('/circle/start')
def http_circle_start():
    ok, msg = circle_start()
    return jsonify(ok=ok, message=msg, running=circle_state['running']), (200 if ok else 409)


@app.post('/circle/stop')
def http_circle_stop():
    ok, msg = circle_stop()
    return jsonify(ok=ok, message=msg, running=circle_state['running']), (200 if ok else 409)


@app.post('/gripper/<action>')
def http_gripper(action):
    ok, msg = do_gripper(action)
    return jsonify(ok=ok, message=msg), (200 if ok else 409)


# ── Recording ─────────────────────────────────────────────────────────────
@app.post('/record/start')
def http_rec_start():
    rec_start()
    return jsonify(ok=True, recording=True)


@app.post('/record/stop')
def http_rec_stop():
    evts = rec_stop()
    return jsonify(ok=True, events=evts)


@app.post('/record/save')
def http_rec_save():
    name = (request.args.get('name') or '').strip()
    # Falls noch live recording läuft, erst stoppen
    if rec_state['recording']:
        rec_stop()
    events = rec_state['events']
    if not events:
        return jsonify(ok=False, message='nichts aufgezeichnet'), 400
    ok, msg = rec_save(name, events)
    return jsonify(ok=ok, message=msg), (200 if ok else 400)


@app.get('/record/list')
def http_rec_list():
    return jsonify(recordings=rec_list(),
                   recording=rec_state['recording'],
                   playing=rec_state['playing'],
                   play_name=rec_state['play_name'],
                   armed=rec_state['armed'])


@app.post('/record/play/<name>')
def http_rec_play(name):
    ok, msg = rec_play(name)
    return jsonify(ok=ok, message=msg), (200 if ok else 409)


@app.post('/record/play_stop')
def http_rec_play_stop():
    ok, msg = rec_play_stop()
    return jsonify(ok=ok, message=msg)


@app.post('/record/delete/<name>')
def http_rec_delete(name):
    ok = rec_delete(name)
    return jsonify(ok=ok), (200 if ok else 404)


@app.post('/record/arm')
def http_rec_arm():
    name = (request.args.get('name') or '').strip()
    if name and rec_load(name) is None:
        return jsonify(ok=False, message='unbekanntes Recording'), 404
    _pullcord_init()
    with rec_lock:
        rec_state['armed'] = name or None
    log.info(f"Pullcord ARMED: {rec_state['armed']!r}")
    return jsonify(ok=True, armed=rec_state['armed'])


@app.get('/status')
def status():
    return jsonify(
        active=state['active'],
        activated=state['activated'],
        eurobot=eurobot_is_active(),
        last=esp.last_state,
        gripper=gripper_link.open,
        recording=rec_state['recording'],
        playing=rec_state['playing'],
        play_name=rec_state['play_name'],
        armed=rec_state['armed'],
        circle=circle_state['running'],
    )


def _shutdown(*_):
    """Beim Stop des Servers: nur Serial-Port sauber schließen.
    Eurobot.service NICHT automatisch starten — start.sh stoppt teleop genau dann,
    wenn es gleich main.py manuell laufen lassen will. „Aufräumen“ bleibt dem
    Deactivate-Button im UI vorbehalten."""
    if esp.open:
        log.info("Shutdown: closing serial …")
        esp.disconnect()


if __name__ == '__main__':
    import atexit, signal
    atexit.register(_shutdown)
    signal.signal(signal.SIGTERM, lambda *_: (_shutdown(), exit(0)))
    log.info(f"Tele-Op-Server auf 0.0.0.0:{HTTP_PORT}")
    # threaded=True damit /cmd nicht durch lange RX-Reads blockiert
    app.run(host='0.0.0.0', port=HTTP_PORT, threaded=True, debug=False, use_reloader=False)
