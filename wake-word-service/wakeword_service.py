#!/usr/bin/env python3
"""
Peambot wake word service.
Listens on the office mic and broadcasts a UDP trigger when 'Hey Peambot' is detected.
"""

import os
import socket
import time
import numpy as np
import sounddevice as sd
import onnxruntime as ort
from openwakeword.model import Model as OWWModel

MODEL_PATH = os.environ.get(
    "WAKE_MODEL_PATH",
    "/home/jason/peambot/wake-word-training/hey_peambot.onnx"
)
MIC_DEVICE = os.environ.get("WAKE_MIC_DEVICE", None)
THRESHOLD = float(os.environ.get("WAKE_THRESHOLD", "0.5"))
COOLDOWN = float(os.environ.get("WAKE_COOLDOWN", "3.0"))
TARGET_IP = os.environ.get("WAKE_TARGET_IP", "255.255.255.255")
TARGET_PORT = int(os.environ.get("WAKE_TARGET_PORT", "9999"))

SAMPLE_RATE = 16000
CHUNK = 1280  # 80ms at 16kHz
N_FRAMES = 16
N_FEATURES = N_FRAMES * 96  # 1536

def main() -> None:
    print(f"Loading openWakeWord base model (feature extractor)...", flush=True)
    oww = OWWModel()  # No wakeword_model_paths — just want the preprocessor

    print(f"Loading classifier: {MODEL_PATH}", flush=True)
    sess = ort.InferenceSession(MODEL_PATH)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    last_trigger = 0.0

    def callback(indata, frames, time_info, status):
        nonlocal last_trigger
        if status:
            print(f"  [audio status: {status}]", flush=True)

        audio = (indata[:, 0] * 32767).astype(np.int16)
        oww.predict(audio)

        buf = oww.preprocessor.feature_buffer
        if buf.shape[0] < N_FRAMES:
            return

        embedding = buf[-N_FRAMES:, :].flatten().astype(np.float32).reshape(1, N_FEATURES)
        outputs = sess.run(["output_probability"], {"input": embedding})
        score = float(outputs[0][0][1])

        if score > THRESHOLD:
            now = time.monotonic()
            if now - last_trigger >= COOLDOWN:
                last_trigger = now
                ts = time.strftime("%Y-%m-%dT%H:%M:%S")
                print(f"[{ts}] DETECTED score={score:.3f}", flush=True)
                sock.sendto(b"PEAMBOT_WAKE", (TARGET_IP, TARGET_PORT))
                print(f"  TRIGGER sent to {TARGET_IP}:{TARGET_PORT}", flush=True)

    device_arg = int(MIC_DEVICE) if MIC_DEVICE and MIC_DEVICE.isdigit() else MIC_DEVICE
    print(f"Opening mic device={device_arg!r} threshold={THRESHOLD} cooldown={COOLDOWN}s", flush=True)

    with sd.InputStream(
        device=device_arg,
        channels=1,
        samplerate=SAMPLE_RATE,
        blocksize=CHUNK,
        callback=callback,
    ):
        print("Listening... (Ctrl+C to stop)", flush=True)
        try:
            while True:
                sd.sleep(1000)
        except KeyboardInterrupt:
            print("Stopped.", flush=True)

if __name__ == "__main__":
    main()
