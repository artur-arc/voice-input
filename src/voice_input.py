#!/usr/bin/env python3
"""Hold Right Cmd to record speech. Right Option to cycle language mode."""
import json
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import mlx_whisper
from pynput import keyboard
from pynput.keyboard import Key

from paste_util import accessibility_binary, has_accessibility, paste_text

SAMPLE_RATE = 16000
MODEL_REPO = "mlx-community/whisper-large-v3-mlx"
MIN_RECORD_SEC = 0.3
RECORD_KEY = Key.cmd_r
MODE_KEY = Key.alt_r

PREFERRED_MICS = ["EMEET", "USB"]

MODES = [
    {"key": "russian-english", "label": "ru→en", "task": "translate",  "language": "ru"},
    {"key": "russian-russian", "label": "ru→ru", "task": "transcribe", "language": "ru"},
    {"key": "english-russian", "label": "en→en", "task": "transcribe", "language": "en"},
]

CONFIG_FILE = Path(__file__).parent.parent / "voice-input-config.json"
config_lock = threading.Lock()
mode_index = 1


def _read_voice_cfg() -> dict:
    raw = json.loads(CONFIG_FILE.read_text())
    return raw.get("voiceInputConfig", raw)


def load_config() -> None:
    global mode_index
    try:
        vcfg = _read_voice_cfg()
        new_index = mode_index
        for i, m in enumerate(MODES):
            if vcfg.get(m["key"]) is True:
                new_index = i
                break
        with config_lock:
            mode_index = new_index
    except Exception as e:
        print(f"Config load error: {e}")


def save_mode(index: int) -> None:
    try:
        raw = json.loads(CONFIG_FILE.read_text())
    except Exception:
        raw = {}
    vcfg = raw.get("voiceInputConfig", raw)
    for i, m in enumerate(MODES):
        vcfg[m["key"]] = (i == index)
    if "voiceInputConfig" in raw:
        raw["voiceInputConfig"] = vcfg
    else:
        raw = vcfg
    CONFIG_FILE.write_text(json.dumps(raw, indent=4))


def watch_config() -> None:
    last_mtime = 0.0
    while True:
        time.sleep(2)
        try:
            mtime = CONFIG_FILE.stat().st_mtime
            if mtime != last_mtime:
                last_mtime = mtime
                load_config()
                m = current_mode()
                print(f"Config reloaded → mode: {m['label']}")
        except Exception:
            pass


def current_mode() -> dict:
    with config_lock:
        return MODES[mode_index]


def notify(title: str, message: str) -> None:
    subprocess.Popen(
        ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def play(sound: str) -> None:
    subprocess.Popen(
        ["afplay", f"/System/Library/Sounds/{sound}.aiff"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def pick_input_device() -> tuple[int | None, str]:
    devices = sd.query_devices()
    for needle in PREFERRED_MICS:
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0 and needle.lower() in d["name"].lower():
                return i, d["name"]
    default = sd.query_devices(kind="input")
    return None, default["name"]


load_config()

input_device, input_name = pick_input_device()
print(f"Mic: {input_name}")
print(f"Loading {MODEL_REPO}...")
mlx_whisper.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), path_or_hf_repo=MODEL_REPO, language="en", verbose=False)

m = current_mode()
ax_ok = has_accessibility()
print(f"Ready. Mode: {m['label']} | accessibility: {'✓' if ax_ok else '✗ (paste disabled)'}")
if not ax_ok:
    print("  → Add to Accessibility: System Settings > Privacy & Security > Accessibility")
    print(f"  → Binary: {accessibility_binary()}")
notify("Voice Input", f"Ready · {m['label']}" + ("" if ax_ok else " · no paste"))

threading.Thread(target=watch_config, daemon=True).start()

state_lock = threading.Lock()
recording = False
audio_chunks: list = []
stream: sd.InputStream | None = None


def cycle_mode() -> None:
    global mode_index
    with config_lock:
        mode_index = (mode_index + 1) % len(MODES)
    save_mode(mode_index)
    m = current_mode()
    print(f"Mode → {m['label']}")
    notify("Voice Input", f"Mode: {m['label']}")
    play("Tink")


def start_recording() -> None:
    global recording, audio_chunks, stream
    with state_lock:
        if recording:
            return
        recording = True
        audio_chunks = []

        def cb(indata, *_):
            audio_chunks.append(indata.copy())

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                device=input_device,
                callback=cb,
            )
            stream.start()
        except Exception as e:
            recording = False
            print(f"Mic error: {e}")
            play("Funk")
            return
    play("Tink")


def stop_and_transcribe() -> None:
    global recording, stream
    with state_lock:
        if not recording:
            return
        recording = False
        if stream is not None:
            stream.stop()
            stream.close()
            stream = None
        if not audio_chunks:
            return
        audio = np.concatenate(audio_chunks).flatten()

    if len(audio) < SAMPLE_RATE * MIN_RECORD_SEC:
        return

    threading.Thread(target=_transcribe_and_paste, args=(audio,), daemon=True).start()


def _transcribe_and_paste(audio: np.ndarray) -> None:
    m = current_mode()
    try:
        t0 = time.time()
        # Whisper initial_prompt primes the model for the target language context.
        # The Russian string is intentional — it improves Russian transcription accuracy.
        initial_prompt = (
            "Привет, давайте обсудим задачу." if m["language"] == "ru" else
            "Let's discuss the task."
        )
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=MODEL_REPO,
            task=m["task"],
            language=m["language"],
            initial_prompt=initial_prompt,
            verbose=False,
        )
        text = result["text"].strip()

        if not text:
            print(f"[{time.time() - t0:.1f}s] (no speech detected)")
            play("Funk")
            return

        elapsed = time.time() - t0
        print(f"[{elapsed:.1f}s] [{m['label']}] {text}")

        pasted = paste_text(text)
        if not pasted:
            print("  (text in clipboard — grant Accessibility to enable auto-paste)")
        play("Pop")
    except Exception as e:
        print(f"Error: {e}")
        play("Funk")


def on_press(key):
    if key == RECORD_KEY:
        start_recording()
    elif key == MODE_KEY:
        cycle_mode()


def on_release(key):
    if key == RECORD_KEY:
        stop_and_transcribe()


with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
