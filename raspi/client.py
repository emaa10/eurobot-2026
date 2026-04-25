#!/usr/bin/env python3
"""
Eurobot 2026 – Interaktive Shell-GUI

    python3 raspi/client.py

Schritt-für-Schritt Oberfläche zur Konfiguration und Spielsteuerung.
Verbindet sich mit main.py auf localhost:5001.
"""

import asyncio
import curses
import threading
import queue
import json
import os
import re

HOST = '127.0.0.1'
PORT = 5001

_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_DIR, '.tactic_config.json')

TACTIC_LABELS_DEFAULT = {
    1: "8 Stück",
    2: "4 Stück, Homologation",
    3: "Taktik 3",
    4: "Taktik 4",
}

STEP_TEAM   = 0
STEP_TACTIC = 1
STEP_MATCH  = 2


# ─── Taktik-Beschreibungen laden / speichern ─────────────────────────────────

def load_labels() -> dict[int, str]:
    labels = dict(TACTIC_LABELS_DEFAULT)
    try:
        with open(CONFIG_FILE) as f:
            for k, v in json.load(f).items():
                n = int(k)
                if n in (3, 4):
                    labels[n] = v
    except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
        pass
    return labels


def save_labels(labels: dict[int, str]):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({str(k): labels[k] for k in (3, 4)}, f)
    except Exception:
        pass


# ─── Netzwerk-Thread ──────────────────────────────────────────────────────────

class NetThread(threading.Thread):
    """Asyncio-Loop in eigenem Thread. Kommunikation via thread-safe Queues."""

    def __init__(self):
        super().__init__(daemon=True)
        self._cmd_q: queue.Queue[str | None] = queue.Queue()
        self.log_q:  queue.Queue[str]        = queue.Queue()
        self.connected = threading.Event()
        self.error: str | None = None
        self._writer: asyncio.StreamWriter | None = None

    def send(self, cmd: str):
        self._cmd_q.put(cmd)

    def stop(self):
        self._cmd_q.put(None)

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._main())

    async def _main(self):
        try:
            reader, writer = await asyncio.open_connection(HOST, PORT)
            self._writer = writer
        except Exception as e:
            self.error = str(e)
            self.connected.set()
            return

        self.connected.set()
        recv = asyncio.create_task(self._recv(reader))
        send = asyncio.create_task(self._send())
        done, pending = await asyncio.wait([recv, send],
                                           return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        self.log_q.put('__DISCONNECTED__')

    async def _recv(self, reader: asyncio.StreamReader):
        while True:
            try:
                data = await reader.readline()
                if not data:
                    return
                self.log_q.put(data.decode().rstrip())
            except asyncio.CancelledError:
                return
            except Exception as e:
                self.log_q.put(f'[Empfang-Fehler: {e}]')
                return

    async def _send(self):
        loop = asyncio.get_running_loop()
        while True:
            cmd = await loop.run_in_executor(None, self._cmd_q.get)
            if cmd is None:
                return
            if self._writer and not self._writer.is_closing():
                try:
                    self._writer.write((cmd + '\n').encode())
                    await self._writer.drain()
                except Exception:
                    return


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

_ANSI_RE = re.compile(r'\033\[[0-9;]*m')

def strip_ansi(s: str) -> str:
    return _ANSI_RE.sub('', s)


def safe_addstr(win, y: int, x: int, text: str, attr: int = 0):
    """addstr das bei Rand-Überschreitung still fehlschlägt."""
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    text = text[:w - x - 1]
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


# ─── Haupt-App ────────────────────────────────────────────────────────────────

class App:
    def __init__(self, stdscr):
        self.scr     = stdscr
        self.step    = STEP_TEAM
        self.team    = 0          # 0 = blau, 1 = gelb
        self.tactic  = 0          # 0-3 → Taktik 1-4
        self.labels  = load_labels()
        self.logs:  list[str] = []
        self.scroll = 0           # Zeilen vom Ende zurück
        self._status: dict[str, str] = {}
        self._net: NetThread | None = None
        self._init_colors()

    def _init_colors(self):
        curses.start_color()
        curses.use_default_colors()
        # pair 1: Header / Rahmen
        curses.init_pair(1, curses.COLOR_YELLOW,  -1)
        # pair 2: OK / aktiv
        curses.init_pair(2, curses.COLOR_GREEN,   -1)
        # pair 3: Hinweise / Tastenkürzel
        curses.init_pair(3, curses.COLOR_CYAN,    -1)
        # pair 4: Fehler
        curses.init_pair(4, curses.COLOR_RED,     -1)
        # pair 5: Ausgewähltes Element (invers)
        curses.init_pair(5, curses.COLOR_BLACK,   curses.COLOR_WHITE)
        # pair 6: LOG-Zeilen
        curses.init_pair(6, curses.COLOR_WHITE,   -1)
        # pair 7: Team-Blau
        curses.init_pair(7, curses.COLOR_WHITE,   curses.COLOR_BLUE)
        # pair 8: Team-Gelb
        curses.init_pair(8, curses.COLOR_BLACK,   curses.COLOR_YELLOW)

    # ── Einstieg ─────────────────────────────────────────────────────────────

    def run(self):
        curses.curs_set(0)
        self.scr.timeout(150)

        # Verbindungs-Screen
        self._draw_connecting()

        self._net = NetThread()
        self._net.start()

        if not self._net.connected.wait(timeout=4.0):
            self._fatal("Timeout – keine Verbindung zu main.py\n"
                        "(systemctl status eurobot)")
            return
        if self._net.error:
            self._fatal(f"Verbindungsfehler: {self._net.error}\n\n"
                        "Läuft main.py?  (systemctl status eurobot)")
            return

        self._loop()
        self._net.stop()

    def _draw_connecting(self):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        msg = f"Verbinde mit {HOST}:{PORT} …"
        safe_addstr(self.scr, h // 2, max(0, (w - len(msg)) // 2),
                    msg, curses.color_pair(3))
        self.scr.refresh()

    def _fatal(self, msg: str):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        lines = msg.split('\n')
        y0 = max(0, h // 2 - len(lines) // 2)
        for i, line in enumerate(lines):
            safe_addstr(self.scr, y0 + i, max(0, (w - len(line)) // 2),
                        line, curses.color_pair(4))
        safe_addstr(self.scr, min(h - 1, y0 + len(lines) + 1), 2,
                    "Drücke eine Taste …", curses.color_pair(3))
        self.scr.refresh()
        self.scr.timeout(-1)
        self.scr.getch()

    # ── Haupt-Schleife ────────────────────────────────────────────────────────

    def _loop(self):
        while True:
            self._drain_logs()
            self._draw()
            key = self.scr.getch()
            if key == curses.ERR:
                continue
            if self._handle_key(key) == 'quit':
                break

    def _drain_logs(self):
        while True:
            try:
                line = self._net.log_q.get_nowait()
            except queue.Empty:
                break
            if line == '__DISCONNECTED__':
                self.logs.append('[Verbindung getrennt]')
            else:
                self.logs.append(line)
                self._parse_status(line)

    def _parse_status(self, line: str):
        clean = strip_ansi(line).strip()
        for field in ('state', 'team', 'tactic', 'pos', 'lidar', 'pullcord'):
            if clean.lstrip().startswith(field + ' ') or clean.lstrip().startswith(field + '\t'):
                val = clean.split(None, 1)[-1] if len(clean.split()) > 1 else ''
                self._status[field] = val

    # ── Zeichnen ──────────────────────────────────────────────────────────────

    def _draw(self):
        self.scr.erase()
        {STEP_TEAM:   self._draw_team,
         STEP_TACTIC: self._draw_tactic,
         STEP_MATCH:  self._draw_match}[self.step]()
        self.scr.refresh()

    def _header(self, title: str):
        _, w = self.scr.getmaxyx()
        bar = f"── {title} " + "─" * max(0, w - len(title) - 4)
        safe_addstr(self.scr, 0, 0, bar[:w - 1],
                    curses.color_pair(1) | curses.A_BOLD)

    def _footer(self, hints: str):
        h, w = self.scr.getmaxyx()
        safe_addstr(self.scr, h - 2, 0, "─" * (w - 1), curses.color_pair(1))
        safe_addstr(self.scr, h - 1, 1, hints[:w - 2], curses.color_pair(3))

    # ── Schritt 1: Team ───────────────────────────────────────────────────────

    def _draw_team(self):
        h, w = self.scr.getmaxyx()
        self._header("EUROBOT 2026  ─  Schritt 1 / 2: Teamfarbe")

        cy = h // 2

        blue_attr   = curses.color_pair(7) | curses.A_BOLD
        yellow_attr = curses.color_pair(8) | curses.A_BOLD
        dim_attr    = curses.color_pair(6)

        blau_lbl = "   BLAU   "
        gelb_lbl = "   GELB   "
        gap = 6
        total = len(blau_lbl) + gap + len(gelb_lbl)
        bx = max(1, (w - total) // 2)
        gx = bx + len(blau_lbl) + gap

        safe_addstr(self.scr, cy, bx, blau_lbl,
                    blue_attr if self.team == 0 else dim_attr)
        safe_addstr(self.scr, cy, gx, gelb_lbl,
                    yellow_attr if self.team == 1 else dim_attr)

        # Auswahlpfeil
        if self.team == 0:
            ax = bx + len(blau_lbl) // 2
        else:
            ax = gx + len(gelb_lbl) // 2
        safe_addstr(self.scr, cy - 2, ax, "▼", curses.color_pair(2) | curses.A_BOLD)

        self._footer("← →  wählen      Enter  bestätigen      Q  beenden")

    # ── Schritt 2: Taktik ─────────────────────────────────────────────────────

    def _draw_tactic(self):
        h, w = self.scr.getmaxyx()
        team_str = "BLAU" if self.team == 0 else "GELB"
        self._header(f"EUROBOT 2026  ─  Schritt 2 / 2: Taktik    Team: {team_str}")

        start_y = max(2, h // 2 - 3)
        for i, num in enumerate([1, 2, 3, 4]):
            y = start_y + i * 2
            if y >= h - 3:
                break
            lbl   = self.labels[num]
            sel   = (i == self.tactic)
            arrow = "▶" if sel else " "
            edit  = "  [E]" if num in (3, 4) else ""

            left  = f"  {arrow}  {num}   {lbl}"
            right = edit
            pad   = w - len(left) - len(right) - 3
            line  = left + " " * max(1, pad) + right

            attr = curses.color_pair(5) | curses.A_BOLD if sel else curses.color_pair(6)
            safe_addstr(self.scr, y, 1, line[:w - 2], attr)

        self._footer("↑ ↓  wählen    1-4  direkt    E  Beschreibung bearbeiten"
                     "    ←  zurück    Enter  bestätigen    Q  beenden")

    # ── Schritt 3: Match ──────────────────────────────────────────────────────

    def _draw_match(self):
        h, w = self.scr.getmaxyx()
        team_str  = "BLAU" if self.team == 0 else "GELB"
        t_num     = self.tactic + 1
        t_desc    = self.labels[t_num]
        state     = self._status.get('state', '…').upper()

        self._header(
            f"EUROBOT 2026  │  {team_str}  │  Taktik {t_num}: {t_desc}  │  {state}"
        )

        log_h = h - 4
        total = len(self.logs)
        end   = total - self.scroll
        start = max(0, end - log_h)
        visible = self.logs[start:end] if end > 0 else []

        for i, line in enumerate(visible):
            clean = strip_ansi(line)
            safe_addstr(self.scr, 1 + i, 1, clean[:w - 2], self._log_attr(line))

        # Scroll-Hinweis
        if self.scroll > 0:
            hint = f"↑ {self.scroll} Zeilen zurück  (↓ vorwärts)"
            safe_addstr(self.scr, h - 3, w - len(hint) - 2,
                        hint, curses.color_pair(3))

        self._footer(
            "[R] Ready    [S] Stop    [← / B] Zurück    "
            "[↑ ↓] Scrollen    [Q] Beenden"
        )

    def _log_attr(self, line: str) -> int:
        c = strip_ansi(line)
        if c.startswith('OK'):
            return curses.color_pair(2)
        if c.startswith('ERR') or 'Fehler' in c:
            return curses.color_pair(4)
        if '───' in c or '──' in c:
            return curses.color_pair(1)
        if 'getrennt' in c.lower() or 'DISCONNECTED' in c:
            return curses.color_pair(4)
        return curses.color_pair(6)

    # ── Tastaturverarbeitung ──────────────────────────────────────────────────

    def _handle_key(self, key: int) -> str | None:
        return {STEP_TEAM:   self._key_team,
                STEP_TACTIC: self._key_tactic,
                STEP_MATCH:  self._key_match}[self.step](key)

    def _key_team(self, key: int) -> str | None:
        if key in (curses.KEY_LEFT, curses.KEY_RIGHT, ord('\t')):
            self.team = 1 - self.team
        elif key in (ord('1'),):
            self.team = 0
        elif key in (ord('2'),):
            self.team = 1
        elif key in (curses.KEY_ENTER, 10, 13):
            self.step = STEP_TACTIC
        elif key in (ord('q'), ord('Q')):
            return 'quit'
        return None

    def _key_tactic(self, key: int) -> str | None:
        if key == curses.KEY_UP:
            self.tactic = (self.tactic - 1) % 4
        elif key == curses.KEY_DOWN:
            self.tactic = (self.tactic + 1) % 4
        elif key in (ord('1'), ord('2'), ord('3'), ord('4')):
            self.tactic = int(chr(key)) - 1
        elif key in (ord('e'), ord('E')):
            num = self.tactic + 1
            if num in (3, 4):
                self._edit_label(num)
        elif key in (curses.KEY_ENTER, 10, 13):
            team_str = 'blue' if self.team == 0 else 'yellow'
            self._net.send(f'team {team_str}')
            self._net.send(f'tactic {self.tactic + 1}')
            self._net.send('status')
            self.scroll = 0
            self.step = STEP_MATCH
        elif key in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 127):
            self.step = STEP_TEAM
        elif key in (ord('q'), ord('Q')):
            return 'quit'
        return None

    def _key_match(self, key: int) -> str | None:
        if key in (ord('r'), ord('R')):
            self._net.send('ready')
        elif key in (ord('s'), ord('S')):
            self._net.send('stop')
        elif key == curses.KEY_UP:
            self.scroll = min(self.scroll + 3, max(0, len(self.logs) - 1))
        elif key == curses.KEY_DOWN:
            self.scroll = max(0, self.scroll - 3)
        elif key in (curses.KEY_LEFT, ord('b'), ord('B')):
            self.scroll = 0
            self.step = STEP_TACTIC
        elif key in (ord('q'), ord('Q')):
            return 'quit'
        return None

    # ── Beschreibung bearbeiten ───────────────────────────────────────────────

    def _edit_label(self, num: int):
        """Inline-Editor für Taktik-Beschreibungen 3 und 4."""
        h, w = self.scr.getmaxyx()
        original = self.labels[num]
        buf      = list(original)
        cur      = len(buf)

        self.scr.timeout(-1)   # Blocking während Edit
        curses.curs_set(1)

        start_y  = max(2, h // 2 - 3)
        y        = start_y + (num - 1) * 2
        prefix   = f"  ▶  {num}   "
        field_x  = 1 + len(prefix)
        max_w    = w - field_x - 4

        while True:
            # Zeile neu zeichnen
            line = (prefix + ''.join(buf))[:w - 2]
            safe_addstr(self.scr, y, 1, ' ' * (w - 3),
                        curses.color_pair(5) | curses.A_BOLD)
            safe_addstr(self.scr, y, 1, line,
                        curses.color_pair(5) | curses.A_BOLD)
            # Editier-Hinweis
            hint = "  Enter=OK   Esc=Abbrechen"
            safe_addstr(self.scr, y + 1, 1, hint, curses.color_pair(3))
            try:
                self.scr.move(y, field_x + cur)
            except curses.error:
                pass
            self.scr.refresh()

            k = self.scr.getch()
            if k in (curses.KEY_ENTER, 10, 13):
                break
            elif k == 27:                           # ESC
                buf = list(original)
                break
            elif k in (curses.KEY_BACKSPACE, 127, 8):
                if cur > 0:
                    buf.pop(cur - 1)
                    cur -= 1
            elif k == curses.KEY_DC:
                if cur < len(buf):
                    buf.pop(cur)
            elif k == curses.KEY_LEFT:
                cur = max(0, cur - 1)
            elif k == curses.KEY_RIGHT:
                cur = min(len(buf), cur + 1)
            elif k == curses.KEY_HOME:
                cur = 0
            elif k == curses.KEY_END:
                cur = len(buf)
            elif 32 <= k <= 126 and len(buf) < max_w:
                buf.insert(cur, chr(k))
                cur += 1

        curses.curs_set(0)
        self.scr.timeout(150)

        new = ''.join(buf).strip()
        if new:
            self.labels[num] = new
            save_labels(self.labels)


# ── Entry point ───────────────────────────────────────────────────────────────

def _main(stdscr):
    App(stdscr).run()


if __name__ == '__main__':
    try:
        curses.wrapper(_main)
    except KeyboardInterrupt:
        print("\nAbgebrochen")
