# voice-input

A background tool for macOS: hold right Cmd, speak, release — the text gets inserted into the active application.

## How it works

| Action | What happens |
|---|---|
| Hold right Cmd → speak → release | Records, transcribes/translates, and pastes text |
| Right Option | Cycles through language modes |

Sounds: Tink on recording start, Pop on success, Funk on error. A macOS notification appears when the mode changes and on startup.

## Installation

One command does everything:

```bash
git clone https://github.com/artur-arc/voice-input && cd voice-input && ./setup.sh
```

`setup.sh` installs Homebrew and Python 3.9+ if missing, creates a virtual environment, installs dependencies, and registers a launchd agent to start automatically on login.

During installation, three System Settings panels will open automatically — grant the following permissions:

1. Microphone
2. Input Monitoring
3. Accessibility

The Whisper model (~1.5 GB) downloads on first run. About 2 GB of disk space required in total.

Requirements: macOS 12+, Python 3.9+ (setup.sh installs it automatically).

## Language modes

Right Option cycles through modes in order:

| Mode | What it does |
|---|---|
| `ru→en` | Russian speech → English text (translation) |
| `ru→ru` | Russian speech → Russian text (transcription) |
| `en→en` | English speech → English text (transcription) |

The current mode persists across restarts in [voice-input-config.json](voice-input-config.json). You can change it in two ways:

- **At runtime** — press Right Option; the app cycles through modes and updates the file automatically.
- **Manually** — open [voice-input-config.json](voice-input-config.json) and set exactly one key to `true`, the rest to `false`:

```json
{
    "russian-english": false,
    "russian-russian": true,
    "english-russian": false
}
```

## Background service

```bash
./install_launchd.sh            # install and start
./install_launchd.sh stop       # stop (will start again on next login)
./install_launchd.sh uninstall  # remove permanently
```

## Logs

```bash
tail -f voice_input.log
```
