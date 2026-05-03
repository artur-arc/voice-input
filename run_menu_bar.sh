#!/bin/bash
# Entry point for the menu bar launchd agent.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] run_menu_bar.sh: starting menu bar"

if [ ! -d .venv ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] run_menu_bar.sh: .venv not found — run setup.sh first"
    exit 1
fi

exec .venv/bin/python -u src/menu_bar.py
