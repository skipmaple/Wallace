# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wallace is an anthropomorphic desktop AI robot combining an ESP32-S3 microcontroller with a PC server. GPLv3 licensed.

## Architecture

**Two-tier system:**
- **ESP32-S3 (N32R16V)**: Hardware I/O — microphone (INMP441/I2S), speaker (MAX98357A/I2S), round LCD (GC9A01/SPI), sensors (DHT20, BH1750, VL53L0X, MQ135), touch (TTP223), RGB LED (WS2812B)
- **PC Server (Python FastAPI)**: AI pipeline — ASR (Faster-Whisper) → LLM (Ollama/deepseek-r1:8b) → TTS (Edge-TTS/CosyVoice), connected via WebSocket

**Data flow**: Wake → mic capture → WebSocket `/ws/{user_id}` → ASR → LLM (streaming) → sentence splitting → TTS → PCM audio frames back via WebSocket. Emotion tags `[mood:xxx]` extracted from LLM output drive ESP32 facial expressions.

**Server module architecture** (`server/wallace/`):
- `config.py` — Pydantic Settings loading from `config/default.toml`, env var overrides with `WALLACE_` prefix
- `ws/protocol.py` — All WebSocket message types as Pydantic models, bidirectional (ESP32↔Server)
- `ws/session.py` — Per-connection Session object with state machine (IDLE→RECORDING→PROCESSING→SPEAKING→IDLE)
- `ws/handler.py` — WebSocket endpoint, JSON message routing, heartbeat monitor
- `pipeline/orchestrator.py` — Chains ASR→LLM→TTS with streaming sentence splitting and interruption support
- `pipeline/asr.py` — Faster-Whisper wrapper, runs transcription in `asyncio.to_thread`
- `pipeline/llm.py` — Ollama HTTP streaming client, 4 personality modes, conversation history window
- `pipeline/tts.py` — Dual backend (EdgeTTS with MP3→PCM transcode via miniaudio, CosyVoice direct PCM), auto-fallback
- `emotion.py` — Regex extraction of `[mood:xxx]` tags, 8 mood enum values
- `sensor.py` — Sensor data caching, LLM context generation, threshold alerts with debounce
- `memory/store.py` — JSON file persistence per user, atomic writes, change detection, sync throttle
- `care/scheduler.py` — APScheduler 3.x async jobs (sedentary/morning/evening), weather API, conflict-aware push
- `smarthome/mqtt.py` — aiomqtt wrapper, scene automation (sleep/wakeup), command forwarding
- `wakeword.py` — openWakeWord placeholder for wake word secondary confirmation
- `app.py` — FastAPI factory with lifespan (init order: ASR→LLM→TTS→MQTT→Sensor→Scheduler→Handler)

Full architecture spec: `server/architecture.md`

## Commands

All server commands run from `server/` directory with the venv at `server/.venv/`.

```bash
# Activate venv (Windows)
server\.venv\Scripts\activate

# Install dependencies (including dev)
pip install -e ".[dev]"

# Run all unit + integration tests
python -m pytest tests/unit tests/integration -v

# Run a single test file
python -m pytest tests/unit/test_llm.py -v

# Run a single test class or method
python -m pytest tests/unit/test_llm.py::TestSystemPrompt::test_contains_personality -v

# Run with coverage
python -m pytest tests/unit tests/integration --cov=wallace --cov-report=term-missing

# E2E tests (requires Ollama running locally, skipped in CI)
python -m pytest tests/e2e -v

# Lint
ruff check wallace/ tests/

# Start server
uvicorn wallace.app:create_app --factory --host 0.0.0.0 --port 8000
```

## TDD Rule (MANDATORY)

Tests already exist for all server modules. When implementing or modifying code:

1. **Tests are the spec** — read the corresponding test file BEFORE writing implementation code. The test cases define the expected behavior; your implementation must satisfy them, not the other way around.
2. **Do NOT modify tests to make them pass** — if a test fails, fix the source code. The only acceptable reason to change a test is when the test itself has a bug (wrong assertion logic), in which case you MUST explain why the old expectation was wrong.
3. **Run tests after every change** — a modification is NOT considered complete until all tests are green.

## Post-Edit Rule

Every time you finish modifying code in the `server/` or `firmware/` directory, you MUST:
1. Re-read `server/architecture.md`
2. Check if your changes are inconsistent with the architecture description
3. If inconsistent, update `server/architecture.md` to reflect the current code
4. Run the corresponding tests: `cd server && python -m pytest tests/unit tests/integration -v`
5. If any test fails, fix the code until all tests pass
6. If you changed the test expectations (not the source code), explain why the old expectation was wrong

## Language Note

Documentation is written in Chinese (中文).
