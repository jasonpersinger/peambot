# Secrets Handling

## Rule

No API keys belong in this repository.

Use local-only files such as `.env`, Docker secrets, or the xiaozhi server's private config store. Keep examples as placeholders only.

## Exposed Keys

Any key pasted into chat, shell logs, screenshots, issue trackers, or committed files should be considered exposed. Rotate it before using it on the deployed server.

The project brief included live-looking keys for:

- Gemini
- Groq
- ElevenLabs
- mem0ai

Rotate those before real testing.

## Local `.env` Shape

Use names like these, with real values only on the Pi or local dev machine:

```dotenv
GEMINI_API_KEY=
GROQ_API_KEY=
ELEVENLABS_API_KEY=
MEM0_API_KEY=
```

Provider-specific base URLs and model names should be recorded in deployment docs without embedding secret values.

