# Peambot Server Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy xinnan-tech/xiaozhi-esp32-server on voidberry (192.168.1.103) with Gemini/Groq/EdgeTTS or ElevenLabs/mem0ai/SileroVAD, a custom Python MCP server exposing Pi-hole + system + weather tools, and ESP32 firmware pointed at the local WebSocket endpoint.

**Architecture:** The main xiaozhi-esp32-server container handles the ESP32 WebSocket, while a sidecar peambot-mcp-server container exposes five MCP tools via SSE on port 8001. API keys live only in `.env` on voidberry; a gen-config.py script substitutes them into the YAML config template before first run.

**Tech Stack:** Docker Compose, xinnan-tech/xiaozhi-esp32-server (Python), fastmcp 2.x (Python MCP SSE server), OpenWeatherMap API, Pi-hole admin API v5, rsync/SSH for deployment.

---

## File Map

```
/home/jason/peambot/
├── .gitignore                              NEW — excludes .env, data/.config.yaml, models/
├── .env.example                            NEW — key shape, no real values
├── docker-compose.yml                      NEW — two services, volumes, restart policies
├── scripts/
│   └── gen-config.py                       NEW — substitutes .env vars into YAML template
├── data/
│   ├── .config.yaml.template               NEW — YAML with ${VAR} placeholders
│   └── .mcp_server_settings.json           NEW — points xiaozhi MCP client at sidecar
└── mcp-server/
    ├── Dockerfile                          NEW — python:3.11-slim, runs server.py
    ├── requirements.txt                    NEW — fastmcp, requests
    └── server.py                           NEW — 5 MCP tools (pihole x3, system, weather)
```

---

## Task 1: Project baseline files

**Files:**
- Create: `.gitignore`
- Create: `.env.example`

- [ ] **Step 1: Write .gitignore**

```gitignore
.env
data/.config.yaml
models/
mcp-server/__pycache__/
**/__pycache__/
*.pyc
*.pyo
```

- [ ] **Step 2: Write .env.example**

```dotenv
# Copy to .env on voidberry and fill in real values — never commit .env
GEMINI_API_KEY=
GROQ_API_KEY=
ELEVENLABS_API_KEY=
MEM0_API_KEY=
OWM_API_KEY=
# Pi-hole v6: use the admin password or a dedicated app password.
PIHOLE_PASSWORD=
PIHOLE_HOST=192.168.1.103
PIHOLE_PORT=8080
```

- [ ] **Step 3: Commit**

```bash
cd /home/jason/peambot
git init
git add .gitignore .env.example
git commit -m "chore: project baseline — gitignore and env template"
```

---

## Task 2: MCP server

**Files:**
- Create: `mcp-server/requirements.txt`
- Create: `mcp-server/server.py`
- Create: `mcp-server/Dockerfile`

- [ ] **Step 1: Write requirements.txt**

```text
fastmcp>=2.0.0
requests>=2.31.0
```

- [ ] **Step 2: Write server.py**

Use the current repository implementation in `mcp-server/server.py`. It targets
Pi-hole v6 session authentication (`POST /api/auth` with `PIHOLE_PASSWORD`), uses
`/api/stats/summary` and `/api/dns/blocking`, reads host CPU/uptime through
read-only `/host` mounts, and reports host disk usage via `/host/root`.

- [ ] **Step 3: Write Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8001
CMD ["python", "server.py"]
```

- [ ] **Step 4: Verify server.py imports resolve (local sanity check)**

```bash
cd /home/jason/peambot/mcp-server
python3 -c "import ast; ast.parse(open('server.py').read()); print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 5: Commit**

```bash
cd /home/jason/peambot
git add mcp-server/
git commit -m "feat: MCP sidecar server — pihole, system stats, weather tools"
```

---

## Task 3: docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Write docker-compose.yml**

```yaml
services:
  xiaozhi-esp32-server:
    image: ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_latest
    container_name: xiaozhi-esp32-server
    restart: unless-stopped
    security_opt:
      - seccomp:unconfined
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
      - /:/host/root:ro
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
    env_file:
      - .env
```

- [ ] **Step 2: Validate YAML syntax**

```bash
cd /home/jason/peambot
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml')); print('YAML OK')"
```

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: docker-compose — xiaozhi server + MCP sidecar, restart:unless-stopped"
```

---

## Task 4: Config template and MCP settings

**Files:**
- Create: `data/.config.yaml.template`
- Create: `data/.mcp_server_settings.json`
- Create: `scripts/gen-config.py`

- [ ] **Step 1: Create data/ directory**

```bash
mkdir -p /home/jason/peambot/data /home/jason/peambot/scripts
```

- [ ] **Step 2: Write data/.config.yaml.template**

```yaml
server:
  ip: 0.0.0.0
  port: 8000
  http_port: 8003
  websocket: ws://192.168.1.103:8000/xiaozhi/v1/
  vision_explain: http://192.168.1.103:8003/mcp/vision/explain
  timezone_offset: +0
  auth:
    enabled: false

prompt: |
  You are Peambot, a helpful AI desk assistant running on a Raspberry Pi.
  You are concise, friendly, and practical. You have tools to check the weather,
  query Pi-hole ad-blocking stats, and read system health metrics for the machine
  you run on. Keep answers brief and conversational — this is a voice interface.

wakeup_words:
  - "Hey Peambot"
  - "Peambot"
  - "Hey Pam"

selected_module:
  VAD: SileroVAD
  ASR: GroqASR
  LLM: GeminiLLM
  TTS: EdgeTTS
  Memory: mem0ai
  Intent: function_call

Intent:
  function_call:
    type: function_call
    functions: []

LLM:
  GeminiLLM:
    type: gemini
    api_key: "${GEMINI_API_KEY}"
    model_name: "gemini-2.0-flash"
    http_proxy: ""
    https_proxy: ""

ASR:
  GroqASR:
    type: openai
    api_key: "${GROQ_API_KEY}"
    base_url: https://api.groq.com/openai/v1/audio/transcriptions
    model_name: whisper-large-v3-turbo
    output_dir: tmp/

TTS:
  EdgeTTS:
    type: edge
    voice: en-US-BrianNeural
    language: English
    volume: "+200%"
    format: mp3
    output_dir: tmp/
  ElevenLabsTTS:
    type: custom
    method: POST
    url: "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM?output_format=mp3_44100_128"
    params:
      text: "{prompt_text}"
      model_id: "eleven_multilingual_v2"
    headers:
      xi-api-key: "${ELEVENLABS_API_KEY}"
    format: mp3
    output_dir: tmp/

VAD:
  SileroVAD:
    type: silero
    threshold: 0.5
    threshold_low: 0.3
    model_dir: models/snakers4_silero-vad
    min_silence_duration_ms: 200

Memory:
  mem0ai:
    type: mem0ai
    api_key: "${MEM0_API_KEY}"
```

- [ ] **Step 3: Write data/.mcp_server_settings.json**

```json
{
  "mcpServers": {
    "peambot-tools": {
      "url": "http://peambot-mcp-server:8001/sse"
    }
  }
}
```

- [ ] **Step 4: Write scripts/gen-config.py**

```python
#!/usr/bin/env python3
"""Substitute .env values into data/.config.yaml.template → data/.config.yaml."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def main() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        print(f"ERROR: {env_path} not found. Copy .env.example and fill in values.", file=sys.stderr)
        sys.exit(1)

    env = load_env(env_path)
    template = (ROOT / "data" / ".config.yaml.template").read_text()

    for key, val in env.items():
        template = template.replace(f"${{{key}}}", val)

    remaining = re.findall(r"\$\{[A-Z_]+\}", template)
    if remaining:
        print(f"WARNING: unfilled placeholders: {', '.join(sorted(set(remaining)))}", file=sys.stderr)

    out = ROOT / "data" / ".config.yaml"
    out.write_text(template)
    print(f"Generated {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Make gen-config.py executable and test syntax**

```bash
chmod +x /home/jason/peambot/scripts/gen-config.py
python3 -c "import ast; ast.parse(open('/home/jason/peambot/scripts/gen-config.py').read()); print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 6: Commit**

```bash
cd /home/jason/peambot
git add data/.config.yaml.template data/.mcp_server_settings.json scripts/gen-config.py
git commit -m "feat: config template, MCP settings, gen-config script"
```

---

## Task 5: Deploy to voidberry

**Prerequisites:** Tasks 1–4 complete. Real API keys ready.

- [ ] **Step 1: Rsync project to voidberry (excluding secrets and models)**

```bash
rsync -avz \
  --exclude='.env' \
  --exclude='data/.config.yaml' \
  --exclude='models/' \
  --exclude='.git/' \
  /home/jason/peambot/ \
  jason@192.168.1.103:~/peambot/
```

Expected: file list ending with `sent N bytes ... total size is N`

- [ ] **Step 2: SSH to voidberry and create .env with real keys**

```bash
ssh jason@192.168.1.103
cd ~/peambot
cp .env.example .env
nano .env   # fill in all six keys
```

Fill every variable:
```
GEMINI_API_KEY=<rotated key from Google AI Studio>
GROQ_API_KEY=<rotated key from console.groq.com>
ELEVENLABS_API_KEY=<rotated key from elevenlabs.io>
MEM0_API_KEY=<rotated key from app.mem0.ai>
OWM_API_KEY=<key from openweathermap.org>
PIHOLE_PASSWORD=<Pi-hole v6 admin password or app password>
PIHOLE_HOST=192.168.1.103
PIHOLE_PORT=8080
```

- [ ] **Step 3: Generate .config.yaml**

```bash
# still on voidberry in ~/peambot
python3 scripts/gen-config.py
```

Expected: `Generated /home/jason/peambot/data/.config.yaml`
No `WARNING: unfilled placeholders` lines should appear.

- [ ] **Step 4: Create models directory (SileroVAD will populate on first run)**

```bash
mkdir -p ~/peambot/models
```

- [ ] **Step 5: Exit SSH**

```bash
exit
```

---

## Task 6: Build and start Docker on voidberry

- [ ] **Step 1: SSH to voidberry**

```bash
ssh jason@192.168.1.103
cd ~/peambot
```

- [ ] **Step 2: Pull the xiaozhi server image**

```bash
docker compose pull xiaozhi-esp32-server
```

Expected: `server_latest: Pull complete` (or `Image is up to date`)

- [ ] **Step 3: Build the MCP sidecar**

```bash
docker compose build peambot-mcp-server
```

Expected: `=> exporting to image ... DONE` with no errors.

- [ ] **Step 4: Start both services**

```bash
docker compose up -d
```

Expected:
```
[+] Running 2/2
 ✔ Container peambot-mcp-server    Started
 ✔ Container xiaozhi-esp32-server  Started
```

- [ ] **Step 5: Check both containers are running**

```bash
docker compose ps
```

Expected: both services in `running` state, not `restarting`.

- [ ] **Step 6: Tail logs for startup errors**

```bash
docker compose logs -f --tail=50
```

Watch for:
- `xiaozhi-esp32-server` starting up and saying server is ready on port 8000
- `peambot-mcp-server` starting fastmcp/uvicorn on port 8001
- SileroVAD model download (first run only — may take a few minutes)
- No `api_key` missing errors

Press Ctrl-C to stop tailing when startup looks clean.

---

## Task 7: Smoke tests

Run these from voidberry (via SSH) or from local machine on the same LAN.

- [ ] **Step 1: Verify MCP sidecar responds**

```bash
curl -s -N --max-time 3 http://192.168.1.103:8001/sse | head -5
```

Expected: SSE event stream starting with `event:` or `data:` lines, or an HTTP 200 with `text/event-stream` content-type.

- [ ] **Step 2: Verify OTA endpoint returns correct WebSocket URL**

```bash
curl -s http://192.168.1.103:8003/xiaozhi/ota/ \
  -H "Content-Type: application/json" \
  -d '{"version":"2.2.6"}' | python3 -m json.tool
```

Expected JSON contains `"websocket": "ws://192.168.1.103:8000/xiaozhi/v1/"`.
If the response format differs, check `docker compose logs xiaozhi-esp32-server | grep ota`.

- [ ] **Step 3: Verify WebSocket port is open**

```bash
nc -zv 192.168.1.103 8000
```

Expected: `succeeded!` or `open`

- [ ] **Step 4: Verify containers survive a restart**

```bash
docker compose down && docker compose up -d && docker compose ps
```

Expected: both services back in `running` state within 30 seconds.

- [ ] **Step 5: Verify restart-on-boot policy**

```bash
# Check Docker daemon is enabled (should already be on Raspberry Pi OS)
ssh jason@192.168.1.103 "sudo systemctl is-enabled docker"
```

Expected: `enabled`

- [ ] **Step 6 (on ESP32): Point firmware at voidberry**

On the ESP32 web config UI (connect ESP32 to WiFi in AP mode → visit http://192.168..4.1):
- Set WebSocket server to: `192.168.1.103`
- Set WebSocket port to: `8000`
- Set WebSocket path to: `/xiaozhi/v1/`

OR let OTA push the config: boot the ESP32 with it pointed at `192.168.1.103:8003` as the OTA server and it will receive the WebSocket URL automatically.

- [ ] **Step 7: End-to-end voice test**

Wake word "Hey Peambot" → ask "What's the weather in London?" 
Expected: spoken weather response using ElevenLabs TTS.

Ask "How is voidberry doing?" 
Expected: spoken CPU temp, uptime, and disk usage.

---

## Troubleshooting Notes

**SileroVAD fails to download:** The container needs outbound internet access. Run `docker exec xiaozhi-esp32-server curl -s https://api.github.com` to verify. If the model dir is populated from a previous run, delete `./models/snakers4_silero-vad/` to force re-download.

**ElevenLabs returns 401:** The `xi-api-key` header value in `.config.yaml` is wrong. Re-run `python3 scripts/gen-config.py` after correcting `.env` and restart with `docker compose restart xiaozhi-esp32-server`.

**MCP tools not appearing to LLM:** Confirm `.mcp_server_settings.json` is in `./data/` and the file is named exactly `.mcp_server_settings.json`. Check `docker compose logs xiaozhi-esp32-server | grep -i mcp`.

**Pi-hole stats return empty:** The Pi-hole v6 password/app password may be wrong or Pi-hole may not be running on `PIHOLE_HOST:PIHOLE_PORT`. Test auth from voidberry with `curl -X POST "http://192.168.1.103:8080/api/auth" --json '{"password":"YOUR_PASSWORD"}'`.
