#!/usr/bin/env python3
"""Hold Right Cmd to record speech. Right Option to cycle language mode."""
import json
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import pyperclip
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import keyboard
from pynput.keyboard import Controller, Key

SAMPLE_RATE = 16000
MODEL_SIZE = "medium"
MIN_RECORD_SEC = 0.3
RECORD_KEY = Key.cmd_r
MODE_KEY = Key.alt_r

PREFERRED_MICS = ["EMEET", "USB"]

# task="translate" → always outputs English
# task="transcribe" → outputs in the source language
MODES = [
    {"key": "russian-english", "label": "ru→en", "task": "translate",  "language": "ru"},
    {"key": "russian-russian", "label": "ru→ru", "task": "transcribe", "language": "ru"},
    {"key": "english-russian", "label": "en→en", "task": "transcribe", "language": "en"},
]

CONFIG_FILE = Path(__file__).parent / "voice-input-config.json"


def load_mode_index() -> int:
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            for i, m in enumerate(MODES):
                if cfg.get(m["key"]) is True:
                    return i
        except Exception:
            pass
    return 1  # default: russian-russian


def save_mode(index: int) -> None:
    cfg = {m["key"]: (i == index) for i, m in enumerate(MODES)}
    CONFIG_FILE.write_text(json.dumps(cfg, indent=4))


mode_index = load_mode_index()


def current_mode() -> dict:
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


input_device, input_name = pick_input_device()
print(f"Mic: {input_name}")
print(f"Loading {MODEL_SIZE} model...")
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

m = current_mode()
print(f"Ready. Mode: {m['label']} | Right Cmd = record | Right Option = cycle mode\n")
notify("Voice Input", f"Ready · {m['label']}")

kb = Controller()
state_lock = threading.Lock()
recording = False
audio_chunks: list = []
stream: sd.InputStream | None = None


def cycle_mode() -> None:
    global mode_index
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
        segments, _ = model.transcribe(
            audio,
            task=m["task"],
            language=m["language"],
            beam_size=5,
            vad_filter=True,
        )
        text = "".join(s.text for s in segments).strip()
        elapsed = time.time() - t0

        if not text:
            print(f"[{elapsed:.1f}s] (no speech detected)")
            play("Funk")
            return

        print(f"[{elapsed:.1f}s] [{m['label']}] {text}")
        pyperclip.copy(text)
        time.sleep(0.05)
        with kb.pressed(Key.cmd):
            kb.press("v")
            kb.release("v")
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
