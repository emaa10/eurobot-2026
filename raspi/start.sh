#!/usr/bin/env bash
# Eurobot 2026 – Interaktiver Start (via SSH auf dem Raspi)
set -euo pipefail

cd "$(dirname "$0")"

echo "══════════════════════════════════════"
echo "  Eurobot 2026 – Start"
echo "══════════════════════════════════════"
echo ""

# ── Team-Auswahl ──────────────────────────────────────────────────────────
while true; do
    printf "  Team  [b]lau / [g]elb: "
    read -r input
    case "${input,,}" in
        b|bl|blau|blue)    TEAM="blue";   break ;;
        g|ge|gelb|yellow)  TEAM="yellow"; break ;;
        *) echo "  → Bitte 'b' (Blau) oder 'g' (Gelb) eingeben." ;;
    esac
done

echo ""
echo "  Team:  $TEAM"
echo ""

# ── Laufenden Service stoppen ─────────────────────────────────────────────
if systemctl is-active --quiet eurobot.service 2>/dev/null; then
    echo "  Stoppe laufenden eurobot.service …"
    sudo systemctl stop eurobot.service
fi

echo "  Starte Eurobot …"
echo "──────────────────────────────────────"
exec python3 -u main.py --team "$TEAM"
