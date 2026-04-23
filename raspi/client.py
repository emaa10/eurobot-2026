#!/usr/bin/env python3
"""
Eurobot 2026 – Remote CLI

Aufruf (per SSH auf dem Raspi):
    python3 raspi/client.py

Verbindet sich mit dem laufenden main.py auf localhost:5001.
Eingaben werden als Befehle gesendet, Server-Antworten und Logs werden
live angezeigt.
"""

import asyncio
import sys
import readline  # aktiviert automatisch Pfeiltasten/History im input()

HOST   = '127.0.0.1'
PORT   = 5001
PROMPT = '\033[96m>\033[0m '   # Cyan-Pfeil als Prompt


async def recv_loop(reader: asyncio.StreamReader, prompt_state: list):
    """Empfängt Zeilen vom Server und gibt sie aus."""
    while True:
        try:
            data = await reader.readline()
            if not data:
                _print_over_prompt("[Verbindung getrennt]", prompt_state)
                return
            line = data.decode().rstrip()
            _print_over_prompt(_colorize(line), prompt_state)
        except asyncio.CancelledError:
            return
        except Exception as e:
            _print_over_prompt(f"[Recv-Fehler: {e}]", prompt_state)
            return


def _colorize(line: str) -> str:
    """Einfache Farb-Markierung je nach Präfix."""
    if line.startswith('OK'):
        return f"\033[92m{line}\033[0m"      # Grün
    if line.startswith('ERR'):
        return f"\033[91m{line}\033[0m"      # Rot
    if line.startswith('LOG'):
        return f"\033[90m{line}\033[0m"      # Grau
    if line.startswith('───') or line.startswith('──'):
        return f"\033[93m{line}\033[0m"      # Gelb (Status-Rahmen)
    return line


def _print_over_prompt(line: str, prompt_state: list):
    """Gibt eine Server-Zeile aus ohne den laufenden Prompt zu zerstören."""
    if prompt_state[0]:
        print(f"\r\033[K{line}\n{PROMPT}", end='', flush=True)
    else:
        print(line)


async def input_loop(writer: asyncio.StreamWriter, prompt_state: list):
    """Liest Befehle vom Nutzer und sendet sie an den Server."""
    loop = asyncio.get_running_loop()
    while True:
        prompt_state[0] = False
        try:
            cmd = await loop.run_in_executor(None, lambda: input(PROMPT))
            prompt_state[0] = True
        except (EOFError, KeyboardInterrupt):
            return

        cmd = cmd.strip()
        if not cmd:
            continue
        if cmd in ('exit', 'quit', 'q'):
            return

        try:
            writer.write((cmd + '\n').encode())
            await writer.drain()
        except Exception as e:
            print(f"[Send-Fehler: {e}]")
            return


async def main():
    print(f"Verbinde mit {HOST}:{PORT} …")
    try:
        reader, writer = await asyncio.open_connection(HOST, PORT)
    except ConnectionRefusedError:
        print("Keine Verbindung – läuft main.py? (systemctl status eurobot)")
        sys.exit(1)
    except Exception as e:
        print(f"Fehler: {e}")
        sys.exit(1)

    # prompt_state[0] == True: Nutzer gibt gerade etwas ein (Prompt sichtbar)
    prompt_state = [False]

    recv_task  = asyncio.create_task(recv_loop(reader, prompt_state))
    input_task = asyncio.create_task(input_loop(writer, prompt_state))

    done, pending = await asyncio.wait(
        [recv_task, input_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass

    print("\nGetrennt.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAbgebrochen")
