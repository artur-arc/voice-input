# voice-input

Hold <kbd>⌘ Right Cmd</kbd>, speak, release — the transcribed text is pasted at the cursor in any app: browser, notes, chat, code editor, any text field.
A microphone icon in the menu bar gives access to all settings. <kbd>⌥ Right Option</kbd> cycles language modes as a secondary shortcut.

macOS uses mlx-whisper on Apple Silicon (Neural Engine). Windows uses faster-whisper on CPU.

## Requirements

| | macOS | Windows |
|---|---|---|
| Hardware | Apple Silicon (M1/M2/M3/M4) | x86_64 |
| OS | macOS 12+ | Windows 10+ |
| Python | installed automatically | installed automatically |
| Git | installed automatically | — |
| Disk | ~2 GB | ~2 GB |

## Installation

### macOS

1. Press <kbd>⌘</kbd><kbd>Space</kbd>, type `Terminal`, press Enter.
2. Paste this command and press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/artur-arc/voice-input/main/install.command | bash
```

The script installs Python, downloads the Whisper model (~1.5 GB), registers autostart, and opens
the permission dialogs for Microphone, Input Monitoring, and Accessibility. When it finishes, a
microphone icon appears in the menu bar and the app starts at every login.

### Windows

[**Download install.bat**](https://raw.githubusercontent.com/artur-arc/voice-input/main/install.bat)
*(if it opens as text in your browser, right-click the link → Save Link As)*

Double-click `install.bat`. The installer downloads and installs Python 3.12, downloads the Whisper
model (~1.5 GB), and registers autostart. When it finishes, a microphone icon appears in the system
tray and the app starts at every login. After installation, grant microphone access when Windows
prompts — or follow the steps in the Permissions section below if the prompt was missed.

## Permissions

### macOS permissions

All three permissions must be granted to **python3** — the binary at `~/voice-input/.venv/bin/python3`. This is the process that runs the voice input service. Terminal only appears in the permission lists if you ran the installer manually; the launchd service itself runs as Python.

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

### Windows permissions

Microphone is the only permission required on Windows. No special steps are needed for hotkey
detection or text pasting.

If the app is not recording, open **Settings → Privacy & Security → Microphone** and check that
"Microphone access" is on and the app is listed and allowed.

## Hotkeys

| Action | macOS | Windows |
|---|---|---|
| Record audio, transcribe, paste | <kbd>⌘ Right Cmd</kbd> (hold → release) | <kbd>Right Ctrl</kbd> (hold → release) |
| Cycle language modes | <kbd>⌥ Right Option</kbd> (tap) | — |

Language mode and microphone can also be changed from the menu bar icon (macOS) or system
tray icon (Windows).

Audio feedback: Tink on recording start, Pop on success, Funk on error.
A macOS notification appears on mode change and at startup.

## Menu bar

A microphone icon sits in the macOS status bar. Click it for a dropdown menu:

| Item | Description |
|---|---|
| `ru→en` / `ru→ru` / `en→en` | Language mode — radio checkmarks, one active at a time |
| `Auto-select` / device names | Microphone — radio checkmarks, one active at a time |
| `Permissions` | Shows grant status for Microphone, Input Monitoring, and Accessibility; click any item to open the relevant System Settings panel |
| `Version 1.0.0` | Current version (informational) |
| `Restart to Update` | Checks GitHub for a new version; pulls and restarts automatically if found |
| `Quit` | Stop the service |

Changes take effect immediately — no restart needed for language or microphone selection.

## Language modes

Right Option cycles through the three modes in order:

| Mode | Config key | What it does |
|---|---|---|
| `ru→en` | `russian-english` | Russian speech → English text (Whisper translation) |
| `ru→ru` | `russian-russian` | Russian speech → Russian text (transcription) |
| `en→en` | `english-english` | English speech → English text (transcription) |

Mode can also be selected from the menu bar (click icon → choose mode).

Note: Whisper's translate task only outputs English. A Russian-output translation mode is not
possible with this model.

## Microphone selection

Click the menu bar icon and select any listed device. The choice takes effect on the next recording. `Auto-select` prefers any EMEET or USB device and falls back to the system default.

As an alternative, [download select_mic.command](https://raw.githubusercontent.com/artur-arc/voice-input/main/select_mic.command) *(if it opens as text in your browser, right-click the link → Save Link As)* and double-click it in Finder. Terminal lists available microphones and lets you pick one interactively. The selection is saved to `voice-input-config.json`.

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

`install_launchd.sh` manages two launchd agents: `com.user.voice-input` (transcription service)
and `com.user.voice-input-menu` (menu bar app). Both start at login and are controlled together:

```bash
./install_launchd.sh            # install and start both
./install_launchd.sh stop       # stop both (restart at next login)
./install_launchd.sh uninstall  # remove both permanently
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
