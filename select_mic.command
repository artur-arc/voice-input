#!/bin/bash
# Voice Input — Microphone Selector
# Double-click this file in Finder to choose your input device.

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "Please run install.command first."
    read -n1 -r -p "Press any key to close..."
    exit 1
fi

.venv/bin/python3 << 'EOF'
import json
import sys
from pathlib import Path

try:
    import sounddevice as sd
except ImportError:
    print("sounddevice not installed. Run install.command first.")
    sys.exit(1)

CONFIG_FILE = Path("voice-input-config.json")

devices = sd.query_devices()
inputs = [
    {"index": i, "name": d["name"]}
    for i, d in enumerate(devices)
    if d["max_input_channels"] > 0
]

if not inputs:
    print("No input devices found.")
    sys.exit(1)

try:
    raw: dict = json.loads(CONFIG_FILE.read_text())
except Exception:
    raw = {}

current: str | None = raw.get("input_device")

print()
print("Voice Input — Microphone Selector")
print("─" * 40)
print()
print("Available microphones:")
print()
for n, dev in enumerate(inputs):
    tag = "  ← active" if current and current.lower() in dev["name"].lower() else ""
    print(f"  [{n}] {dev['name']}{tag}")
auto_tag = "  ← active" if not current else ""
print(f"  [a] Auto-select (EMEET/USB › system default){auto_tag}")
print()

try:
    choice = input("Enter number or 'a' to auto-select [a]: ").strip()
except (EOFError, KeyboardInterrupt):
    print("\nCancelled.")
    sys.exit(0)

if choice == "" or choice.lower() == "a":
    raw["input_device"] = None
    label = "auto-select"
else:
    try:
        idx = int(choice)
        if not (0 <= idx < len(inputs)):
            raise ValueError
        raw["input_device"] = inputs[idx]["name"]
        label = inputs[idx]["name"]
    except ValueError:
        print(f"\nInvalid choice: {choice!r}")
        sys.exit(1)

CONFIG_FILE.write_text(json.dumps(raw, indent=4))
print()
print(f"✓ Saved. Microphone set to: {label}")
print("  No restart needed — takes effect on next recording.")
print()
EOF

read -n1 -r -p "Press any key to close..."
