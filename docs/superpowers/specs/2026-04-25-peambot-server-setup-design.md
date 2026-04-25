# Peambot Server Setup Design

**Date:** 2026-04-25  
**Status:** Approved

---

## Overview

Self-hosted AI desk assistant running on a Waveshare ESP32-S3-Touch-AMOLED-1.8 with
xiaozhi-esp32 v2.2.6 firmware, backed by xinnan-tech/xiaozhi-esp32-server on a
Raspberry Pi 4B ("voidberry", 192.168.1.103).

---

## Architecture

```
voidberry (192.168.1.103)
├── Docker: xiaozhi-esp32-server      ports 8000 (WS), 8003 (HTTP/OTA)
│     ├── data/.config.yaml           provider selection + keys (not in git)
│     └── data/.mcp_server_settings.json  → points at peambot-mcp-server
│
├── Docker: peambot-mcp-server        port 8001 (SSE)
│     ├── tools/pihole.py             Pi-hole stats / pause / resume
│     ├── tools/system.py             CPU temp, uptime, disk
│     └── tools/weather.py            OpenWeatherMap current conditions
│
└── Shared Docker volume: ./models/   SileroVAD model cache

ESP32 → ws://192.168.1.103:8000/xiaozhi/v1/
        (URL pushed to device via OTA from server.websocket config field)
```

---

## Provider Stack

| Slot   | Provider            | Config key        | Notes |
|--------|---------------------|-------------------|-------|
| LLM    | Gemini 2.0 Flash    | `GeminiLLM`       | native `gemini` type |
| ASR    | Groq Whisper        | `GroqASR`         | `openai` type with Groq base URL |
| TTS    | ElevenLabs          | `ElevenLabsTTS`   | `custom` type, POST to ElevenLabs REST API |
| VAD    | SileroVAD           | `SileroVAD`       | local; Torch Hub auto-downloads model |
| Memory | mem0ai              | `mem0ai`          | cloud, 1000 free calls/mo |
| Intent | function_call       | —                 | enables MCP tool dispatch |

---

## ElevenLabs TTS

No native ElevenLabs provider exists. The `custom` TTS type supports arbitrary POST
bodies. ElevenLabs v1 TTS endpoint is:

```
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128
Headers: xi-api-key: KEY, Content-Type: application/json
Body:    {"text": "...", "model_id": "eleven_multilingual_v2"}
```

Config in `.config.yaml`:
```yaml
ElevenLabsTTS:
  type: custom
  method: POST
  url: "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM?output_format=mp3_44100_128"
  params:
    text: "{prompt_text}"
    model_id: "eleven_multilingual_v2"
  headers:
    xi-api-key: "REPLACE_FROM_ENV"
  format: mp3
  output_dir: tmp/
```

Default voice: Rachel (`21m00Tcm4TlvDq8ikWAM`). Swap voice_id in URL to change.

---

## MCP Server

Single Python service using the `mcp` SDK with SSE transport on port 8001.
The main server connects at `http://peambot-mcp-server:8001/sse`.

### Tools

**pihole_get_stats** — returns queries today, blocked count, percent blocked, server status.
Uses Pi-hole API at `http://${PIHOLE_HOST}/admin/api.php`.

**pihole_pause(seconds)** — pauses blocking for N seconds (0 = indefinitely).

**pihole_resume** — resumes blocking.

**system_get_stats** — reads `/host/proc/uptime`, `/host/sys/class/thermal/thermal_zone0/temp`,
`shutil.disk_usage("/")`. Returns formatted string.

**get_weather(city)** — calls OpenWeatherMap Current Weather API v2.5.
Returns current conditions, temperature (°C), humidity, wind speed.

### MCP Server Container

```
mcp-server/
├── Dockerfile
├── requirements.txt
└── server.py           # all five tools in one file
```

Mounts `host /proc → /host/proc:ro` and `host /sys → /host/sys:ro` for system stats.

---

## docker-compose.yml

```yaml
services:
  xiaozhi-server:
    image: ghcr.nju.edu.cn/xinnan-tech/xiaozhi-esp32-server:server_latest
    container_name: xiaozhi-esp32-server
    restart: unless-stopped
    security_opt: [seccomp:unconfined]
    environment:
      - TZ=Europe/London
    ports:
      - "8000:8000"
      - "8003:8003"
    volumes:
      - ./data:/opt/xiaozhi-esp32-server/data
      - ./models:/opt/xiaozhi-esp32-server/models
    depends_on:
      - peambot-mcp-server

  peambot-mcp-server:
    build: ./mcp-server
    container_name: peambot-mcp-server
    restart: unless-stopped
    ports:
      - "8001:8001"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
    env_file: .env
```

---

## Secrets / .env

All API keys live in `.env` on voidberry only. Shape:

```dotenv
GEMINI_API_KEY=
GROQ_API_KEY=
ELEVENLABS_API_KEY=
MEM0_API_KEY=
PIHOLE_API_KEY=
OWM_API_KEY=
PIHOLE_HOST=192.168.1.103
```

The `.config.yaml` references keys by value (not env interpolation — the xiaozhi server
doesn't support env vars in YAML). A deploy script copies `.env` values into
`.config.yaml` at deployment time.

---

## ESP32 Firmware Configuration

The device receives its WebSocket URL via the OTA endpoint at `http://192.168.1.103:8003`.
No firmware modification needed — set `server.websocket: ws://192.168.1.103:8000/xiaozhi/v1/`
in `.config.yaml` and the OTA response carries it to the device on next boot.

Wake word: "Hey Peambot" (custom, set in `wakeup_words` list).

---

## Restart Policy

Both services use `restart: unless-stopped`. Docker daemon itself starts on boot
via systemd (already standard on Raspberry Pi OS).

---

## File Layout on voidberry

```
~/peambot/
├── docker-compose.yml
├── .env                         (not committed)
├── data/
│   ├── .config.yaml             (not committed — contains keys)
│   └── .mcp_server_settings.json
├── models/
│   └── snakers4_silero-vad/     (auto-populated by server on first run)
└── mcp-server/
    ├── Dockerfile
    ├── requirements.txt
    └── server.py
```
