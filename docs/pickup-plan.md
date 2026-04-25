# Peambot Pickup Plan

## What I Found

The local `/home/jason/peambot` folder was empty, so there is no inherited codebase or competing LLM output to preserve yet. The best immediate work is to create a project control surface: clear docs, sanitized config expectations, and an ordered bring-up checklist.

## Priority 0: Rotate Exposed Keys

The project brief included live-looking Gemini, Groq, ElevenLabs, and mem0ai keys. Treat them as compromised because they appeared in plaintext chat context.

- Revoke or rotate all pasted keys.
- Put replacement values only in private local config.
- Never commit `.env`, generated server config with secrets, shell history exports, or screenshots showing keys.

## Priority 1: Server Bring-Up

Goal: get the Pi running xiaozhi-esp32-server before the ESP32 hardware arrives.

- Prepare Raspberry Pi OS on the SATA SSD.
- Update Pi bootloader if USB boot is not already enabled.
- Install Docker and Docker Compose plugin.
- Clone `xinnan-tech/xiaozhi-esp32-server`.
- Choose minimal Docker deployment with all-API model providers.
- Configure model providers using secret placeholders first.
- Confirm web UI starts on LAN.
- Confirm test tools can reach ASR, LLM, VLLM, TTS, and VAD paths.
- Record measured latency in `docs/latency-notes.md`.

## Priority 2: Provider Compatibility Check

The intended stack is sensible, but it needs a config-level check against the current server release.

- Confirm Gemini OpenAI-compatible base URL and model names accepted by the server.
- Confirm whether Groq Whisper is directly supported as an ASR provider.
- Confirm whether ElevenLabs is directly supported as TTS.
- If Groq or ElevenLabs are not direct providers, decide between:
  - adapter shim through an OpenAI-compatible endpoint,
  - built-in provider fallback,
  - small server plugin.

## Priority 3: Firmware Bring-Up

Goal: stock firmware first.

- Use the web flasher or upstream flashing docs for the Waveshare ESP32-S3-Touch-AMOLED-1.8 board.
- Prefer latest stable upstream release after checking release notes.
- Pair to local backend using WebSocket first unless the server docs strongly favor MQTT+UDP for the target config.
- Validate:
  - display initializes at correct orientation,
  - touch does not block boot,
  - mic input reaches server,
  - speaker output works,
  - wake word path works,
  - battery/PMIC state is displayed,
  - OTA behavior is understood.

## Priority 4: MCP Tools

Add one MCP integration at a time after voice loop is stable.

Recommended order:

1. Pi/system status query.
2. Pi-hole status query.
3. voidbox script trigger.
4. Sloplocks pipeline query.
5. Home Assistant control.

Each tool should have a narrow command schema, timeouts, and a harmless dry-run/test mode.

## Priority 5: Camera Board

Do not block the core assistant on camera work.

- Treat the camera board as an independent WiFi sensor.
- Stream frames or snapshots to the Pi.
- Send selected image frames to VLLM from the server side.
- Avoid assuming UART or shared firmware integration between the AMOLED board and camera board.

## Open Questions

- Which protocol should Peambot use first: WebSocket or MQTT+UDP?
- Will the Pi run the web UI only on LAN/Tailscale, or should it have any public exposure?
- Is the robot face expected to use stock xiaozhi emoji assets, custom generated assets, or a custom firmware face renderer?
- Should the camera be a live stream feature, an on-demand "look" command, or both?
- What printer/slicer constraints matter for the enclosure?

