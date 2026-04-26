# Peambot Wake Word — "Hey Peambot"

**Goal:** Trigger Peambot's listening mode by saying "Hey Peambot" from anywhere in the office, without pressing the BOOT button.

**Architecture:** openWakeWord runs as a systemd service on voidbox, listening on the existing office mic. On detection it sends a small UDP packet to the local broadcast address. The ESP32 firmware has a new UDP listener task that calls `StartListening()` on receipt. No changes to voidberry or the Docker stack.

**Tech Stack:** Python 3, openWakeWord 0.4.x (ONNX), sounddevice, ESP-IDF UDP sockets (lwIP), CachyOS systemd

---

## Machines

| Machine | Role | Mic |
|---------|------|-----|
| voidbox (office) | Runs openWakeWord service | Yes — existing office mic |
| voidberry (192.168.1.103, living room) | Runs Docker stack | No change |
| Peambot ESP32 (office) | Receives UDP trigger | No change to mic |

---

## Trigger Flow

```
office mic → openWakeWord (voidbox)
  → UDP broadcast 192.168.1.255:9999 payload "PEAMBOT_WAKE"
  → ESP32 UDP listener task
  → Application::StartListening()
  → eyes go cyan, device listens
```

No voidberry changes. No MCP sidecar changes. The broadcast reaches the ESP32 directly because all devices are on the same /24 subnet.

---

## Component 1: hey_peambot.onnx (trained on voidbox)

openWakeWord supports training from synthetic data — TTS-generated audio samples, no microphone recording required.

### Training process

1. Install training dependencies:
   ```bash
   pip install openwakeword[training] --break-system-packages
   pip install edge-tts --break-system-packages
   ```

2. Generate positive samples — 500 TTS renderings of "Hey Peambot" across multiple edge-tts voices:
   ```bash
   python3 scripts/generate_wake_samples.py
   ```
   Saves to `wake-word-training/positive/`.

3. Download openWakeWord negative sample dataset (~200MB, one-time):
   ```bash
   python3 -c "from openwakeword.utils import download_background_noise; download_background_noise()"
   ```

4. Train the model:
   ```bash
   python3 scripts/train_wake_model.py
   ```
   Outputs `wake-word-training/hey_peambot.onnx`. Takes ~10 minutes on CPU.

5. Test detection threshold interactively before deploying.

### Files

| File | Purpose |
|------|---------|
| `scripts/generate_wake_samples.py` | Generates TTS positive samples using edge-tts voices |
| `scripts/train_wake_model.py` | Trains openWakeWord model, saves ONNX |
| `wake-word-training/positive/` | Generated .wav samples (gitignored) |
| `wake-word-training/hey_peambot.onnx` | Trained model (committed) |

`wake-word-training/positive/` and the background noise cache are gitignored. Only the final `.onnx` is committed.

---

## Component 2: Wake Word Service (voidbox)

A Python script running as a systemd user service. Captures mic audio and feeds it to openWakeWord. On detection above threshold, sends UDP broadcast.

### File: `wake-word-service/wakeword_service.py`

Key behaviour:
- Loads `hey_peambot.onnx` from a configured path
- Opens mic via sounddevice at 16kHz, mono, 1280-sample chunks (80ms)
- Feeds each chunk to `oww_model.predict()`
- Fires trigger when score exceeds `THRESHOLD` (default 0.5)
- After triggering, enforces a 3-second cooldown to prevent double-triggers
- Sends `b"PEAMBOT_WAKE"` as a UDP packet to `255.255.255.255:9999`
- Logs detections with timestamp and score to stdout (captured by journald)

### Config (environment variables or config file)

| Variable | Default | Purpose |
|----------|---------|---------|
| `WAKE_MIC_DEVICE` | `default` | sounddevice device name or index |
| `WAKE_THRESHOLD` | `0.5` | Detection confidence threshold |
| `WAKE_COOLDOWN` | `3.0` | Seconds to suppress after trigger |
| `WAKE_TARGET_IP` | `255.255.255.255` | UDP destination (broadcast or specific IP) |
| `WAKE_TARGET_PORT` | `9999` | UDP destination port |
| `WAKE_MODEL_PATH` | `/home/jason/peambot/wake-word-training/hey_peambot.onnx` | ONNX model path |

### File: `wake-word-service/peambot-wakeword.service`

systemd user unit. Installed to `~/.config/systemd/user/`. Starts on login. Restarts on failure with 5-second delay.

```ini
[Unit]
Description=Peambot Wake Word Detector
After=sound.target

[Service]
ExecStart=/usr/bin/python3 /home/jason/peambot/wake-word-service/wakeword_service.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

---

## Component 3: ESP32 UDP Listener (firmware)

A new FreeRTOS task in the firmware that opens a UDP socket and listens on port 9999. On receiving `"PEAMBOT_WAKE"`, it calls `app.StartListening()`.

### New file: `firmware/main/udp_trigger.h` / `udp_trigger.cc`

The task:
1. Creates a UDP socket bound to `0.0.0.0:9999`
2. Blocks on `recvfrom()` in a loop
3. Validates payload is exactly `"PEAMBOT_WAKE"` (12 bytes)
4. Calls the registered callback (which calls `app.StartListening()`)
5. Enforces a 3-second cooldown (matches service-side cooldown, double protection)

The task is started in `Application::Start()` after WiFi connects (inside the `MAIN_EVENT_NETWORK_CONNECTED` handler).

### Changes to existing files

| File | Change |
|------|--------|
| `firmware/main/udp_trigger.h` | NEW — `UdpTrigger` class with `Start(callback)` |
| `firmware/main/udp_trigger.cc` | NEW — FreeRTOS task, UDP socket, callback dispatch |
| `firmware/main/CMakeLists.txt` | Add `udp_trigger.cc` to SOURCES |
| `firmware/main/application.cc` | Start UDP trigger task on network connect; wire callback to `StartListening()` |

### UDP packet spec

| Field | Value |
|-------|-------|
| Protocol | UDP |
| Destination | Broadcast `255.255.255.255` or ESP32 IP |
| Port | 9999 |
| Payload | `PEAMBOT_WAKE` (12 ASCII bytes, no null terminator) |

Any packet on port 9999 with payload not matching `PEAMBOT_WAKE` is silently dropped.

---

## Security

The UDP trigger is unauthenticated — anyone on the local network can send a `PEAMBOT_WAKE` packet. This is acceptable for a home office network. The worst case is an unintended listen session, not data exfiltration. If this becomes a concern, a shared secret (HMAC or simple pre-shared token) can be added to the packet.

---

## Testing Checklist

- [ ] `hey_peambot.onnx` loads without error
- [ ] Saying "Hey Peambot" scores > 0.5 consistently
- [ ] Saying other phrases scores < 0.3
- [ ] UDP packet reaches ESP32 (verify with `nc -u 255.255.255.255 9999` sending `PEAMBOT_WAKE`)
- [ ] ESP32 transitions to Listening state on packet receipt
- [ ] Cooldown prevents double-trigger (say phrase twice quickly, only one activation)
- [ ] systemd service survives reboot and restarts on crash
- [ ] False positive rate acceptable during normal office conversation

---

## Out of Scope

- HMAC authentication on the UDP packet
- Multi-room detection (second mic in living room)
- Offline training with real voice recordings
- Dynamic threshold tuning UI
