#!/usr/bin/env python3
"""
Eurobot 2026 – Steuerungsclient (SSH-Bedienung)

Verwendung:
    python3 raspi/client.py
    python3 raspi/client.py --host 192.168.x.x   # wenn von anderem Gerät aus

Verbindet sich mit dem TCP-Server in main.py und erlaubt:
  - Teamfarbe / Startposition / Taktik einstellen
  - Homing starten und Spielablauf überwachen
  - Direktbefehle senden (Debug, Manualsteuerung)
"""

import asyncio
import sys
import argparse
from datetime import datetime

# ─── Verbindung ───────────────────────────────────────────────────────────────
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 5001

# ─── Konfigurationstabellen ───────────────────────────────────────────────────
TACTICS = {
    1: "Standard A",
    2: "Standard B",
    3: "Standard C  (mit Homing)",
    4: "TEST – 1 m geradeaus",
}

START_POS = {
    1: "Pos 1 – Links   (x ≈ 150 mm)",
    2: "Pos 2 – Mitte   (x ≈ 600 mm)",
    3: "Pos 3 – Rechts  (x ≈ 1050 mm)",
}

QUICK_CMDS = {
    "gp":  "Position abfragen",
    "es":  "Notfall-Stopp",
    "hg":  "Greifer homen",
    "fd":  "Flagge runter",
    "fu":  "Flagge hoch",
    "dd500":  "500 mm vorwärts",
    "dd-500": "500 mm rückwärts",
    "ta90":   "90° rechts drehen",
    "ta-90":  "90° links drehen",
}

# ─── Anzeige-Hilfsfunktionen ──────────────────────────────────────────────────
def hr(char='─', width=54):
    print(char * width)

def header():
    print()
    hr('═')
    print("  Eurobot 2026 – Steuerungsclient")
    hr('═')

def ts():
    return datetime.now().strftime("%H:%M:%S")

def info(msg):  print(f"  {msg}")
def ok(msg):    print(f"  ✓ {msg}")
def warn(msg):  print(f"  ! {msg}")
def err(msg):   print(f"  ✗ {msg}")

def show_config(pos: int, tac: int):
    hr()
    info(f"Startposition : {pos} – {START_POS.get(pos, '?')}")
    info(f"Taktik        : {tac} – {TACTICS.get(tac, '?')}")
    hr()

def show_menu(pos: int, tac: int):
    show_config(pos, tac)
    print()
    info("p <1-3>   Startposition ändern")
    info("t <1-4>   Taktik ändern")
    info("go        Homing starten")
    info("cmd <x>   Direktbefehl senden")
    info("q <x>     Schnellbefehl  (q? zum Anzeigen)")
    info("es        Notfall-Stopp")
    info("exit      Beenden")
    print()

# ─── Haupt-Client ─────────────────────────────────────────────────────────────
class Client:
    def __init__(self, host: str, port: int):
        self.host   = host
        self.port   = port
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.pos    = 1
        self.tac    = 4
        self.state  = 'config'   # config | homing | waiting_cord | game | done
        self.points = 0

    async def connect(self) -> bool:
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            ok(f"Verbunden mit {self.host}:{self.port}")
            return True
        except ConnectionRefusedError:
            err(f"Verbindung abgelehnt – läuft main.py auf {self.host}:{self.port}?")
            return False
        except OSError as e:
            err(f"Netzwerkfehler: {e}")
            return False

    def send(self, msg: str):
        if not self.writer:
            warn("Nicht verbunden.")
            return
        self.writer.write(msg.encode())
        # drain wird im Event-Loop-Kontext aufgerufen

    async def send_async(self, msg: str):
        if not self.writer:
            warn("Nicht verbunden.")
            return
        self.writer.write(msg.encode())
        await self.writer.drain()

    # ── Empfangsloop (läuft als Hintergrundtask) ─────────────────────────────
    async def recv_loop(self):
        while True:
            try:
                data = await self.reader.read(1024)
                if not data:
                    warn("Server hat Verbindung getrennt.")
                    self.state = 'done'
                    break
                for msg in data.decode().split('\n'):
                    msg = msg.strip()
                    if not msg:
                        continue
                    self._handle_server_msg(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                err(f"Empfangsfehler: {e}")
                self.state = 'done'
                break

    def _handle_server_msg(self, msg: str):
        if msg == 'h':
            print()
            ok("Homing abgeschlossen.")
            warn(">>> Zugschnur ziehen, um das Spiel zu starten! <<<")
            self.state = 'waiting_cord'

        elif msg.startswith('c'):
            try:
                pts = int(msg[1:])
                if pts != -1:
                    self.points = pts
                    print(f"\r  [{ts()}] Punkte: {self.points}   ", end='', flush=True)
                    self.state = 'game'
                else:
                    # -1 = Taktik abgeschlossen
                    print()
                    ok(f"Taktik abgeschlossen. Endpunktestand: {self.points}")
                    self.state = 'done'
            except ValueError:
                pass

        else:
            print(f"\n  [Server {ts()}]: {msg}")

    # ── Eingabe-Loop ──────────────────────────────────────────────────────────
    async def input_loop(self):
        loop = asyncio.get_event_loop()

        show_menu(self.pos, self.tac)

        while self.state != 'done':
            try:
                line = await loop.run_in_executor(None, input, "> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            line = line.strip()
            if not line:
                continue

            parts = line.split()
            cmd   = parts[0].lower()

            # ── Universelle Befehle ──────────────────────────────────────────
            if cmd == 'exit':
                break

            if cmd == 'es':
                await self.send_async('es')
                warn("Notfall-Stopp gesendet.")
                continue

            # ── Konfiguration ────────────────────────────────────────────────
            if cmd == 'p':
                if len(parts) < 2:
                    warn("Verwendung: p <1-3>")
                    continue
                try:
                    v = int(parts[1])
                    if v not in START_POS:
                        raise ValueError
                    self.pos = v
                    ok(f"Startposition: {self.pos} – {START_POS[self.pos]}")
                except ValueError:
                    warn(f"Ungültig. Gültige Positionen: {list(START_POS)}")
                continue

            if cmd == 't':
                if len(parts) < 2:
                    warn("Verwendung: t <1-4>")
                    continue
                try:
                    v = int(parts[1])
                    if v not in TACTICS:
                        raise ValueError
                    self.tac = v
                    ok(f"Taktik: {self.tac} – {TACTICS[self.tac]}")
                except ValueError:
                    warn(f"Ungültig. Gültige Taktiken: {list(TACTICS)}")
                continue

            if cmd == 'show':
                show_menu(self.pos, self.tac)
                continue

            # ── Homing & Spielstart ──────────────────────────────────────────
            if cmd == 'go':
                if self.state not in ('config', 'done'):
                    warn("Homing läuft bereits oder Spiel aktiv.")
                    continue
                show_config(self.pos, self.tac)
                confirm = await loop.run_in_executor(
                    None, input, "  Bestätigen? [j/N] "
                )
                if confirm.strip().lower() != 'j':
                    info("Abgebrochen.")
                    continue
                self.state = 'homing'
                cmd_str = f"st{self.pos};{self.tac}"
                await self.send_async(cmd_str)
                info(f"→ Gesendet: {cmd_str}")
                info("  Homing läuft … (Ausgabe kommt wenn fertig)")
                continue

            # ── Direktbefehl ─────────────────────────────────────────────────
            if cmd == 'cmd':
                if len(parts) < 2:
                    warn("Verwendung: cmd <befehl>  (z.B. cmd dd400)")
                    continue
                raw = ' '.join(parts[1:])
                await self.send_async(raw)
                info(f"→ Gesendet: {raw}")
                continue

            # ── Schnellbefehle ───────────────────────────────────────────────
            if cmd == 'q':
                if len(parts) < 2 or parts[1] == '?':
                    print()
                    info("Verfügbare Schnellbefehle:")
                    for k, v in QUICK_CMDS.items():
                        info(f"  q {k:<10} – {v}")
                    print()
                    continue
                key = parts[1]
                if key not in QUICK_CMDS:
                    warn(f"Unbekannt. 'q ?' zeigt alle Schnellbefehle.")
                    continue
                await self.send_async(key)
                info(f"→ Gesendet: {key}  ({QUICK_CMDS[key]})")
                continue

            warn(f"Unbekannter Befehl '{cmd}'. 'show' zeigt das Menü.")

    # ── Hauptablauf ───────────────────────────────────────────────────────────
    async def run(self):
        header()

        if not await self.connect():
            return

        print()
        info("Team-Farbe wird vom Hardware-Schalter (GPIO 17) gelesen.")
        info("Startposition und Taktik hier einstellen, dann 'go'.")
        print()

        recv_task = asyncio.create_task(self.recv_loop())

        try:
            await self.input_loop()
        finally:
            recv_task.cancel()
            try:
                await recv_task
            except asyncio.CancelledError:
                pass
            if self.writer:
                self.writer.close()
                try:
                    await self.writer.wait_closed()
                except Exception:
                    pass

        print()
        info("Verbindung getrennt. Auf Wiedersehen!")


# ─── Einstiegspunkt ───────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Eurobot 2026 Steuerungsclient")
    parser.add_argument('--host', default=DEFAULT_HOST,
                        help=f"Server-IP (Standard: {DEFAULT_HOST})")
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f"Server-Port (Standard: {DEFAULT_PORT})")
    args = parser.parse_args()

    client = Client(args.host, args.port)
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n  Abgebrochen.")


if __name__ == '__main__':
    main()
