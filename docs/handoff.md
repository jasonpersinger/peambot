# Peambot Handoff

Last updated: 2026-04-26

This document is the current operational handoff for Peambot. It is intended for a future LLM or engineer picking up the project without the original chat history.

## Current State

Peambot is working as a self-hosted voice assistant.

- Hardware: Waveshare ESP32-S3-Touch-AMOLED-1.8.
- Board serial device during bring-up: `/dev/ttyACM0`.
- Server host: `voidberry` at `192.168.1.103`.
- Local repo: `/home/jason/peambot`.
- Remote repo path on Voidberry: `~/peambot`.
- Docker services:
  - `xiaozhi-esp32-server`
  - `peambot-mcp-server`
- Firmware is flashed and activated.
- Wake/activation worked in live testing.
- Wake word detection via openWakeWord on voidbox; "Hey Peambot" triggers listening mode over UDP.
- Voice answers work through Groq ASR, Gemini LLM, EdgeTTS, Silero VAD, mem0ai, and MCP tools.
- Broad live Gemini web/search grounding is available through an MCP tool.

## Important Commits

Recent project history:

- `c4ef421 fix: enable sports winner predictions`
- `53725f2 feat: add broad live Gemini tool`
- `341eb46 feat: add grounded live analysis tools`
- `de497a9 fix: route Gemini tool calls through OpenAI provider`
- `495b66d chore: snapshot Peambot bring-up baseline`
- `03310ee feat: Peambot firmware v1 - robot eyes complete`

Commit signing with GPG timed out during one session, so recent commits were made with `git commit --no-gpg-sign`.

## Repository Layout

- [README.md](../README.md): original project overview, partially stale.
- [docker-compose.yml](../docker-compose.yml): runtime stack for server plus MCP sidecar.
- [data/.config.yaml.template](../data/.config.yaml.template): xiaozhi server config template. Secrets are substituted from `.env`.
- `data/.config.yaml`: generated runtime config with secrets; intentionally ignored.
- [data/.mcp_server_settings.json](../data/.mcp_server_settings.json): points xiaozhi MCP client at the sidecar.
- [mcp-server/server.py](../mcp-server/server.py): all Peambot MCP tools.
- [mcp-server/Dockerfile](../mcp-server/Dockerfile): MCP sidecar image.
- [scripts/gen-config.py](../scripts/gen-config.py): substitutes `.env` values into `data/.config.yaml.template`.
- [firmware/](../firmware): xiaozhi ESP32 firmware tree with Peambot display work.
- [docs/secrets.md](secrets.md): secret handling rules.
- `wake-word-service/wakeword_service.py`: openWakeWord + onnxruntime service; runs on voidbox, broadcasts UDP on detection.
- `wake-word-service/peambot-wakeword.service`: systemd user unit for wakeword_service.py.
- `wake-word-training/hey_peambot.onnx`: trained wake word ONNX model (committed).
- [scripts/generate_wake_samples.py](../scripts/generate_wake_samples.py): generates 500 TTS WAV samples for training.
- [scripts/train_wake_model.py](../scripts/train_wake_model.py): trains the wake word model from positive + synthetic noise samples.

Untracked files present at last handoff and intentionally not touched:

- `.superpowers/`
- `docs/superpowers/plans/2026-04-25-peambot-firmware.md`
- `docs/superpowers/specs/2026-04-25-peambot-firmware-design.md`
- `scripts/test_wakeword.py`

Do not delete or revert these unless the user explicitly asks.

## Runtime Architecture

The ESP32 board connects to `xiaozhi-esp32-server` over WebSocket:

```text
ESP32-S3 AMOLED board
  -> ws://192.168.1.103:8000/xiaozhi/v1/
  -> xiaozhi-esp32-server
  -> GeminiOpenAILLM / GroqASR / EdgeTTS / SileroVAD / mem0ai
  -> MCP client
  -> peambot-mcp-server on http://peambot-mcp-server:8001/sse
```

The MCP sidecar exposes local and live-world tools. The xiaozhi server discovers them through `data/.mcp_server_settings.json`.

Wake word trigger (voidbox only):

```text
office mic
  -> openWakeWord service (voidbox)
  -> UDP broadcast 192.168.1.255:9999 "PEAMBOT_WAKE"
  -> ESP32 UDP listener task (port 9999)
  -> Application::StartListening()
```

## Provider Configuration

The current selected modules in `data/.config.yaml.template` are:

```yaml
selected_module:
  VAD: SileroVAD
  ASR: GroqASR
  LLM: GeminiOpenAILLM
  TTS: EdgeTTS
  Memory: mem0ai
  Intent: function_call
```

The LLM uses the server's OpenAI-compatible provider pointed at Gemini:

```yaml
LLM:
  GeminiOpenAILLM:
    type: openai
    api_key: "${GEMINI_API_KEY}"
    base_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
    model_name: "gemini-2.5-flash"
```

This replaced the native Gemini provider after a live failure:

- User asked: "How hot is Voidberry?"
- ASR recognized correctly.
- Gemini tried to call `system_get_stats`.
- Native Gemini provider failed with a `thought_signature` function-call error.
- Server spoke its default Chinese fallback.

The fix was:

- Add English `system_error_response`.
- Switch main LLM to Gemini through the OpenAI-compatible provider.
- Use `gemini-2.5-flash`.

Google's OpenAI-compatible endpoint rejected `gemini-2.0-flash` for this account as no longer available to new users, so do not revert to it without testing.

## Prompt Policy

The prompt currently tells Peambot:

- Answer in one or two sentences maximum.
- Give facts and numbers directly.
- Always respond in English.
- Use tools for:
  - broad live Gemini web research
  - weather
  - Pi-hole
  - system health
  - news
  - finance
  - sports lineups
  - sports winner predictions
- Use the broad live Gemini tool for current-world, open-ended, research, comparison, recommendation, analysis, or "look it up" requests.
- Use `sports_game_prediction` for sports winner or game prediction questions.

## MCP Tools

Defined in [mcp-server/server.py](../mcp-server/server.py).

Local/home tools:

- `pihole_get_stats()`: Pi-hole status, queries, blocked count, percent blocked, blocklist size.
- `pihole_pause(seconds: int = 0)`: pause blocking.
- `pihole_resume()`: resume blocking.
- `system_get_stats()`: Voidberry CPU temperature, uptime, disk usage.
- `get_weather(city: str)`: current weather via OpenWeatherMap.

Live Gemini grounded tools:

- `ask_gemini_live(query: str)`: broad open-agent tool using Gemini with Google Search grounding.
- `analyze_news(topic: str = "top news in the United States right now")`: current news analysis.
- `financial_update(query: str)`: market/ticker/company/crypto updates. It must not give financial advice.
- `sports_lineup_analysis(query: str)`: lineups, injuries, rosters, matchups, likely winners if asked.
- `sports_game_prediction(query: str)`: sports analyst-style winner picks with low/medium/high confidence. It avoids guarantees and betting instructions.

The live tools call:

```text
https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent
```

with:

```json
"tools": [{"google_search": {}}]
```

The sidecar extracts source names from Gemini grounding metadata and appends source names when useful.

## Secrets

Never print, commit, or paste real values from `.env` or generated config.

Expected `.env` keys include:

```dotenv
GEMINI_API_KEY=
GROQ_API_KEY=
ELEVENLABS_API_KEY=
MEM0_API_KEY=
PIHOLE_HOST=
PIHOLE_PORT=
PIHOLE_PASSWORD=
OWM_API_KEY=
```

Only `.env.example` style placeholders should be committed. See [docs/secrets.md](secrets.md).

## Deployment Commands

From local repo:

```bash
rsync -az mcp-server/server.py data/.config.yaml.template jason@192.168.1.103:~/peambot/ --relative
ssh jason@192.168.1.103 'cd ~/peambot && python3 scripts/gen-config.py >/dev/null && docker compose build peambot-mcp-server && docker compose up -d peambot-mcp-server && docker compose restart xiaozhi-esp32-server'
```

On Voidberry:

```bash
cd ~/peambot
python3 scripts/gen-config.py
docker compose build peambot-mcp-server
docker compose up -d
docker compose restart xiaozhi-esp32-server
docker compose logs --tail=120 xiaozhi-esp32-server
docker compose logs --tail=120 peambot-mcp-server
```

Verify tool registration:

```bash
ssh jason@192.168.1.103 'cd ~/peambot && docker compose logs --tail=160 xiaozhi-esp32-server 2>&1 | grep -E "可用工具|当前支持的函数列表|ask_gemini_live|sports_game_prediction"'
```

Expected tool list includes:

```text
pihole_get_stats
pihole_pause
pihole_resume
system_get_stats
get_weather
ask_gemini_live
analyze_news
financial_update
sports_lineup_analysis
sports_game_prediction
```

Direct sidecar smoke test:

```bash
ssh jason@192.168.1.103 'docker exec -i peambot-mcp-server python -' <<'PY'
import server
print(server.system_get_stats())
print(server.ask_gemini_live("What is the latest stable Python version?")[:500])
print(server.sports_game_prediction("today NBA games most likely winners")[:500])
PY
```

## Firmware State

The board was flashed successfully from this repo's firmware tree.

Observed boot facts:

- App version: `2.2.6`
- Compile time during bring-up: `Apr 26 2026 03:30:41`
- Wi-Fi SSID used in logs: `jp2g`
- OTA current/latest check passed.
- Activation completed.
- Known noisy serial log:
  - `E sh8601: swap_xy is not supported by this panel`
  - This appeared benign.

The Peambot custom face is in `firmware/main/display/peambot_display.cc` and related firmware commits. A warning cleanup removed an unused `TAG` and `esp_log.h` include.

If reflashing:

- Use the ESP-IDF environment already used for this repo.
- Target is ESP32-S3.
- Flash port was `/dev/ttyACM0`.
- Do not assume `/dev/ttyACM0` will always be the path; check `ls /dev/ttyACM*`.

## Known Issues

### mem0ai Save Errors

Server logs have shown:

```text
保存记忆失败: {"messages":["Bad request. Please check memory creation docs..."]}
```

Memory connection succeeds, but saves sometimes fail. This has not blocked voice/tool behavior. Future work should inspect mem0 API request shape or disable memory if it causes latency/noise.

### Broad Gemini Grounded Searches Can Time Out

The live grounded tool uses a 20-second HTTP timeout. A broad model-comparison query hit this timeout once. Smaller live queries succeeded.

Do not blindly increase the timeout too far; voice interaction should not hang. Better future fix: add async/background "research mode" or return a short "still checking" behavior if the server supports it.

### Sports Predictions Are Gemini Analysis, Not a Statistical Model

Current sports picks rely on Gemini with live Google Search grounding. The tool prompt asks Gemini to consider public context such as injuries, lineups, probable starters, standings, recent form, rest, and home/away context.

It does not run a local Elo model, betting market model, projection model, or historical statistical simulation. If the user wants better sports predictions, add a real data source and model layer.

### News Grounding Can Be Overconfident

An early broad news query produced a too-assertive answer. The prompt was tightened to require credible support and avoid inventing breaking events. Continue testing with current-events prompts.

### Chinese Built-In Server Text

The server has some built-in Chinese prompts/log messages, especially around exit intent and errors. The main system error response is now English, but some internal fallback paths may still speak Chinese if triggered.

## User-Facing Test Prompts

Good manual tests after any deployment:

- "Peambot, how hot is Voidberry?"
- "Peambot, what can you do?"
- "Peambot, what's the biggest news story right now?"
- "Peambot, give me a market update on Nvidia."
- "Peambot, analyze today's NBA games and pick the most likely winner."
- "Peambot, look up the latest stable Python version."
- "Peambot, what's the weather in Philadelphia?"
- "Peambot, pause Pi-hole for ten minutes."

## Wake Word Service

The wake word detection service runs as a systemd user unit on voidbox (192.168.1.103) and listens to the office microphone for "Hey Peambot".

Service name: `peambot-wakeword` (systemd user service on voidbox)

Check status:

```bash
systemctl --user status peambot-wakeword.service
```

View logs:

```bash
journalctl --user -u peambot-wakeword.service -n 30
```

Model path:

```text
/home/jason/peambot/wake-word-training/hey_peambot.onnx
```

Tunable environment variables:

- `WAKE_THRESHOLD` (default 0.5): detection confidence threshold; raise to 0.6–0.8 to reduce false positives.
- `WAKE_COOLDOWN` (default 3.0): seconds between consecutive detections.

Known limitation:

The model was trained on synthetic noise negatives. It may have a higher false positive rate against real speech. If false positives occur, tune `WAKE_THRESHOLD` upward (0.6–0.8).

Test manually (from voidbox):

```bash
echo -n "PEAMBOT_WAKE" | nc -u -w1 255.255.255.255 9999
```

This broadcasts a test message to the UDP listener on the ESP32.

## Next Good Work

Highest-value next steps (wake word feature completed):

1. Add a capability manifest tool so "what can you do?" returns a clean feature list.
2. Add a real sports data layer for schedules, injuries, odds/favorites, and model-based picks.
3. Add a finance data layer for deterministic prices before Gemini analysis.
4. Add a local "daily brief" tool that composes weather, Voidberry health, Pi-hole, news, and calendar/tasks if available.
5. Fix or disable mem0ai save errors.
6. Add a longer-form research mode if the voice stack can handle delayed responses.
7. Improve source/citation handling for spoken answers and optional screen display.
8. Reduce false positives in wake word detection by improving the model with real-world speech samples or tuning WAKE_THRESHOLD.

## Working-Tree Rules

This repo may contain user-created untracked files. Do not run destructive git commands like:

```bash
git reset --hard
git checkout -- .
git clean -fd
```

unless the user explicitly asks.

Use `git status --short` before editing. Ignore unrelated untracked planning files unless the task requires them.
