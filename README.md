# Peambot

Self-hosted AI desktop buddy: an ESP32-S3 AMOLED robot face backed by a Raspberry Pi home server running the xiaozhi ecosystem, Gemini-compatible LLM/VLLM, voice I/O, memory, and MCP automation.

## Current Handoff

For the latest operational state, deployment commands, known issues, and next steps, start with [docs/handoff.md](docs/handoff.md). Some older planning notes below are preserved for context and may be stale.

## Current State

- Local project folder was empty when this document was created.
- Primary board is ordered: Waveshare ESP32-S3-Touch-AMOLED-1.8.
- Raspberry Pi 4B is ordered; SSD/enclosure still pending.
- Camera board is planned but not ordered.
- Firmware path is stock `78/xiaozhi-esp32` first, with custom work only after hardware bring-up.
- Backend path is `xinnan-tech/xiaozhi-esp32-server`, Docker minimal install, all-API config.

## Verified Upstream Notes

- `78/xiaozhi-esp32` supports the Waveshare ESP32-S3-Touch-AMOLED-1.8 board and includes wake word, emoji display, MCP, English/Japanese/Chinese, OTA, WebSocket or MQTT+UDP, and ESP32-S3 support.
- The latest GitHub release observed on 2026-04-24 was `v2.2.6`; earlier notes listed `v2.2.4`.
- `xinnan-tech/xiaozhi-esp32-server` provides WebSocket/MQTT+UDP backend service, web management UI, MCP support, VAD, ASR/LLM/TTS integrations, memory options, and Docker deployment docs.
- The latest server release observed on 2026-04-24 was `v0.9.2`.

## Target Hardware

### Assistant Display Board

- Waveshare ESP32-S3-Touch-AMOLED-1.8
- 368x448 AMOLED, SH8601 display driver, FT3168 touch
- ESP32-S3R8, 8MB PSRAM, 16MB flash
- ES8311 audio codec, onboard mic, onboard speaker
- AXP2101 PMIC, battery connector, USB-C

### Optional Camera Board

- Waveshare ESP32-S3-CAM-OV5640
- Independent WiFi device streaming to the Pi server
- Same enclosure, separate board path; do not assume xiaozhi firmware can manage both boards over UART.

### Home Server

- Raspberry Pi 4B 4GB
- USB boot from SATA SSD
- Runs xiaozhi server, Pi-hole, weather display script, and future MCP tools
- Tailscale for private remote access

## Preferred Software Stack

| Role | Preferred | Fallback |
| --- | --- | --- |
| Firmware | `78/xiaozhi-esp32` stock Waveshare config | Custom ESP-IDF fork later |
| Backend | `xinnan-tech/xiaozhi-esp32-server` minimal Docker install | Source deploy |
| LLM | Gemini via OpenAI-compatible interface | Other OpenAI-compatible provider |
| VLLM | Gemini multimodal | Backend-supported VLLM provider |
| ASR | Groq Whisper, if supported in config or via adapter | SherpaASR local |
| TTS | ElevenLabs, if supported in config or via adapter | EdgeTTS |
| VAD | SileroVAD local | Required/default |
| Intent | `function_call` | `nointent` only for debugging |
| Memory | mem0ai | `mem_local_short` |

## Security

Do not commit API keys. Store them in a local `.env` or server-side config file excluded by `.gitignore`. Keys that have appeared in chat or logs should be considered exposed and rotated before real deployment.

See [docs/secrets.md](docs/secrets.md).

## Best Place To Pick Up

Start with the backend and deployment scaffold before touching firmware:

1. Prepare Raspberry Pi OS on SSD and confirm USB boot.
2. Install Docker and bring up xiaozhi-esp32-server minimal all-API config.
3. Configure providers with placeholder env vars, then test model/TTS/ASR latency using the server test tools.
4. Flash stock xiaozhi firmware for the Waveshare board when hardware arrives.
5. Pair board to local server over LAN, confirm wake word, mic, speaker, display face, battery status, and OTA path.
6. Only after the stock path works, add Peambot-specific MCP tools and enclosure/camera work.

The next actionable file is [docs/pickup-plan.md](docs/pickup-plan.md).
