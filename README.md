# voice-input

Hold <kbd>⌘ Right Cmd</kbd>, speak, release — the transcribed text is pasted at the cursor position in any app: browser, notes, chat, code editor, any text field.
Tap <kbd>⌥ Right Option</kbd> to cycle language modes: `ru→en` · `ru→ru` · `en→en`

Runs as a background launchd service on Apple Silicon Macs. Uses mlx-whisper with the
`whisper-large-v3-mlx` model, which runs entirely on the Neural Engine.

## Requirements

- Apple Silicon Mac (arm64 only — mlx-whisper does not run on Intel)
- macOS 12+
- Python 3.11+ (`setup.sh` installs it via Homebrew if missing)
- ~2 GB of disk space for the model and virtual environment
- Three macOS permissions: Microphone, Input Monitoring, Accessibility

## Installation

**Option A (recommended):** [Download install.command](https://github.com/artur-arc/voice-input/raw/main/install.command), then double-click it in Finder. macOS opens Terminal and runs the full install automatically. No Terminal knowledge needed.

**Option B:**

```bash
git clone https://github.com/artur-arc/voice-input && cd voice-input && ./setup.sh
```

Both options handle everything in order: check that you are on Apple Silicon, install Homebrew
and Python 3.11+ if missing, create a virtual environment, install Python packages, download
the Whisper model (~1.5 GB), walk through three permission prompts, and register a launchd
agent so the service starts automatically at login.

> After installation the app starts automatically at every login — no action needed after a reboot.

When the permission prompts appear, find `python` or `Terminal` in each System Settings pane
and enable the toggle.

## Permissions

The installer requests three macOS permissions automatically. If a dialog was missed or a
permission was revoked, grant it manually:

**1. Microphone** — allows the app to record audio.

> System Settings → Privacy & Security → Microphone

If **Terminal** is not in the list:

1. Click **+**
2. Press <kbd>⌘</kbd><kbd>Shift</kbd><kbd>G</kbd> and type `/Applications/Utilities`
3. Select **Terminal.app** → click Open
4. Enable the toggle next to Terminal

**2. Input Monitoring** — allows the app to detect hotkeys globally (even when another app is in focus).

> System Settings → Privacy & Security → Input Monitoring

If **Terminal** is not in the list, follow the same steps as above (click **+** → `/Applications/Utilities` → **Terminal.app**).

**3. Accessibility** — allows the app to simulate <kbd>⌘V</kbd> to paste transcribed text at the cursor.

> System Settings → Privacy & Security → Accessibility

The service runs under Python, not Terminal. If **Python** or **python3** is not in the list:

1. Click **+**
2. Press <kbd>⌘</kbd><kbd>Shift</kbd><kbd>G</kbd> and type `~/voice-input/.venv/bin`
3. Select **python3** → click Open
4. Enable the toggle next to python3

After granting any permission, restart the service:

```bash
./install_launchd.sh stop
./install_launchd.sh install
```

## Hotkeys

| Key | Action |
|---|---|
| <kbd>⌘ Right Cmd</kbd> (hold → release) | Record audio, transcribe, paste |
| <kbd>⌥ Right Option</kbd> (tap) | Cycle language modes |

Audio feedback: Tink on recording start, Pop on success, Funk on error.
A macOS notification appears on mode change and at startup.

## Language modes

Right Option cycles through the three modes in order:

| Mode | Config key | What it does |
|---|---|---|
| `ru→en` | `russian-english` | Russian speech → English text (Whisper translation) |
| `ru→ru` | `russian-russian` | Russian speech → Russian text (transcription) |
| `en→en` | `english-english` | English speech → English text (transcription) |

Note: Whisper's translate task only outputs English. A Russian-output translation mode is not
possible with this model.

## Microphone selection

[Download select_mic.command](https://github.com/artur-arc/voice-input/raw/main/select_mic.command), then double-click it in Finder. Terminal opens and lists every available microphone with its current status:

```text
Voice Input — Microphone Selector
────────────────────────────────────────

Available microphones:

  [0] Galaxy Buds3 (CD78)
  [1] EMEET SmartCam S600  ← active
  [2] MacBook Pro Microphone
  [a] Auto-select (EMEET/USB › system default)

Enter number or 'a' to auto-select [a]:
```

Enter the number of the device you want to pin, then press Enter. The choice is saved to `voice-input-config.json` and takes effect on the next recording — no restart needed.

Pressing Enter without a number (or entering `a`) switches to auto-select: prefers any EMEET or USB device, falls back to the system default.

Use this when connecting a Bluetooth headset or switching between multiple microphones.

## Configuration

The active mode is stored in `voice-input-config.json`. The file is watched live — edits take
effect within two seconds without a restart.

To change the mode manually, set exactly one key to `true` and the rest to `false`:

```json
{
    "voiceInputConfig": {
        "english-english": true,
        "russian-english": false,
        "russian-russian": false
    },
    "input_device": null
}
```

`"input_device"` — device name string to pin a specific mic, or `null` for auto-select.

Pressing Right Option at runtime has the same effect and updates the file automatically.

## Service management

```bash
./install_launchd.sh            # install and start
./install_launchd.sh stop       # stop (restarts at next login)
./install_launchd.sh uninstall  # remove permanently
```

## Logs and troubleshooting

```bash
tail -f voice_input.log
```

Common problems:

- Accessibility not granted: text is copied to the clipboard but Cmd+V is not simulated.
  The log prints `(text in clipboard — grant Accessibility to enable auto-paste)`.
  Fix: System Settings → Privacy & Security → Accessibility, add Python.
- Input Monitoring not granted: hotkeys are not detected. Fix: System Settings →
  Privacy & Security → Input Monitoring, add Python.
- Microphone not granted: recording fails with a mic error in the log.
