# voice-input

Hold Right Cmd, speak, release — the transcribed text gets pasted into whatever app is focused.

Runs as a background launchd service on Apple Silicon Macs. Uses mlx-whisper with the
`whisper-large-v3-mlx` model, which runs entirely on the Neural Engine.

## Requirements

- Apple Silicon Mac (arm64 only — mlx-whisper does not run on Intel)
- macOS 12+
- Python 3.11+ (`setup.sh` installs it via Homebrew if missing)
- ~2 GB of disk space for the model and virtual environment
- Three macOS permissions: Microphone, Input Monitoring, Accessibility

## Installation

**Option A (recommended):** Download `install.command`, then double-click it in Finder. macOS
opens Terminal and runs the full install automatically. No Terminal knowledge needed.

**Option B:**

```bash
git clone https://github.com/artur-arc/voice-input && cd voice-input && ./setup.sh
```

Both options handle everything in order: check that you are on Apple Silicon, install Homebrew
and Python 3.11+ if missing, create a virtual environment, install Python packages, download
the Whisper model (~1.5 GB), walk through three permission prompts, and register a launchd
agent so the service starts automatically at login.

When the permission prompts appear, find `python` or `Terminal` in each System Settings pane
and enable the toggle.

## Hotkeys

| Key | Action |
|---|---|
| Right Cmd (hold → release) | Record audio, transcribe, paste into the active app |
| Right Option | Cycle through language modes |

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

## Configuration

The active mode is stored in `voice-input-config.json`. The file is watched live — edits take
effect within two seconds without a restart.

To change the mode manually, set exactly one key to `true` and the rest to `false`:

```json
{
    "voiceInputConfig": {
        "russian-english": false,
        "russian-russian": true,
        "english-english": false
    }
}
```

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
