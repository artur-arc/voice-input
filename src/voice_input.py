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

from cleanup import TranscriptCleaner

SAMPLE_RATE = 16000
MODEL_SIZE = "medium"
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
cleanup_enabled = False
cleanup_model = "llama3.2"
cleaner: TranscriptCleaner | None = None


def _read_voice_cfg() -> dict:
    raw = json.loads(CONFIG_FILE.read_text())
    return raw.get("voiceInputConfig", raw)


def load_config() -> None:
    global mode_index, cleanup_enabled, cleanup_model, cleaner
    try:
        vcfg = _read_voice_cfg()
        new_index = mode_index
        for i, m in enumerate(MODES):
            if vcfg.get(m["key"]) is True:
                new_index = i
                break
        with config_lock:
            mode_index = new_index
            cleanup_enabled = bool(vcfg.get("cleanup", False))
            cleanup_model = vcfg.get("cleanup_model", "llama3.2")
            cleaner = TranscriptCleaner(cleanup_model) if cleanup_enabled else None
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
                print(f"Config reloaded → mode: {m['label']}, cleanup: {cleanup_enabled} ({cleanup_model})")
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
print(f"Loading {MODEL_SIZE} model...")
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

m = current_mode()
print(f"Ready. Mode: {m['label']} | cleanup: {cleanup_enabled} | Right Cmd = record | Right Option = cycle mode\n")
notify("Voice Input", f"Ready · {m['label']}")

threading.Thread(target=watch_config, daemon=True).start()

kb = Controller()
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
        initial_prompt = (
            "Привет, давайте обсудим задачу." if m["language"] == "ru" else
            "Let's discuss the task."
        )
        segments, _ = model.transcribe(
            audio,
            task=m["task"],
            language=m["language"],
            beam_size=5,
            vad_filter=True,
            initial_prompt=initial_prompt,
        )
        text = "".join(s.text for s in segments).strip()

        if not text:
            print(f"[{time.time() - t0:.1f}s] (no speech detected)")
            play("Funk")
            return

        with config_lock:
            active_cleaner = cleaner

        if active_cleaner is not None:
            text = active_cleaner.clean(text, m["language"])

        elapsed = time.time() - t0
        tag = f"{m['label']}+clean" if active_cleaner is not None else m['label']
        print(f"[{elapsed:.1f}s] [{tag}] {text}")

        pyperclip.copy(text)
        time.sleep(0.1)
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
