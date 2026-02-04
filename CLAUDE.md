# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wallace is an anthropomorphic desktop AI robot combining an ESP32-S3 microcontroller with a PC server. GPLv3 licensed.

**Key features:**
- Voice conversation with 4 personality modes (normal, cool, talkative, tsundere)
- Animated eyes on round LCD with emotion-driven expressions
- Environmental sensing + smart home control via MQTT
- Proactive care: sedentary reminders, morning greetings, weather reports
- Per-user memory persistence for personalized conversations

## Architecture

**Two-tier system:**
- **ESP32-S3 (N32R16V)**: Hardware I/O — microphone (INMP441/I2S), speaker (MAX98357A/I2S), round LCD (GC9A01/SPI), sensors (DHT20, BH1750, VL53L0X, MQ135), touch (TTP223), RGB LED (WS2812B)
- **PC Server (Python FastAPI)**: AI pipeline — ASR (Faster-Whisper) → LLM (Ollama/deepseek-r1:8b) → TTS (Edge-TTS/CosyVoice), connected via WebSocket

**Data flow**: Wake → mic capture → WebSocket `/ws/{user_id}` → ASR → LLM (streaming) → sentence splitting → TTS → PCM audio frames back via WebSocket. Emotion tags `[mood:xxx]` extracted from LLM output drive ESP32 facial expressions.

## Project Structure

```
Wallace/
├── server/                     # PC backend (Python FastAPI)
│   ├── wallace/               # Main package
│   │   ├── app.py            # FastAPI factory + lifespan
│   │   ├── config.py         # Pydantic Settings (TOML loading)
│   │   ├── emotion.py        # Mood tag extraction
│   │   ├── sensor.py         # Sensor data + alerts
│   │   ├── wakeword.py       # Wake word verification
│   │   ├── vision.py         # Optional image analysis
│   │   ├── ws/               # WebSocket layer
│   │   │   ├── protocol.py   # Message type definitions
│   │   │   ├── session.py    # Per-connection state
│   │   │   └── handler.py    # Message routing
│   │   ├── pipeline/         # AI processing
│   │   │   ├── asr.py        # Faster-Whisper
│   │   │   ├── llm.py        # Ollama client
│   │   │   ├── tts.py        # Edge-TTS/CosyVoice
│   │   │   └── orchestrator.py # Pipeline coordination
│   │   ├── memory/           # User persistence
│   │   │   └── store.py      # JSON file storage
│   │   ├── care/             # Proactive features
│   │   │   └── scheduler.py  # APScheduler tasks
│   │   └── smarthome/        # Smart home
│   │       └── mqtt.py       # MQTT client
│   ├── config/
│   │   └── default.toml      # Default configuration
│   ├── tests/
│   │   ├── conftest.py       # Shared fixtures
│   │   ├── unit/             # Unit tests (12 files)
│   │   ├── integration/      # Integration tests (3 files)
│   │   ├── e2e/              # End-to-end tests (8 files)
│   │   └── fixtures/         # Test data files
│   └── pyproject.toml        # Package config
├── doc/                       # Documentation
│   ├── spec.md               # Hardware specifications
│   ├── purchase-list.md      # Bill of materials
│   └── archive/              # Versioned design docs
├── .github/workflows/         # CI/CD
│   └── server-test.yml       # Test automation
└── README.md                  # Project overview
```

## Server Module Architecture

`server/wallace/` module breakdown:

| Module | Purpose |
|--------|---------|
| `config.py` | Pydantic Settings loading from `config/default.toml`, env var overrides with `WALLACE_` prefix |
| `ws/protocol.py` | All WebSocket message types as Pydantic models, bidirectional (ESP32↔Server) |
| `ws/session.py` | Per-connection Session object with state machine (IDLE→RECORDING→PROCESSING→SPEAKING→IDLE) |
| `ws/handler.py` | WebSocket endpoint at `/ws/{user_id}`, JSON message routing, heartbeat monitor |
| `pipeline/orchestrator.py` | Chains ASR→LLM→TTS with streaming sentence splitting and interruption support |
| `pipeline/asr.py` | Faster-Whisper wrapper, runs transcription in `asyncio.to_thread` |
| `pipeline/llm.py` | Ollama HTTP streaming client, 4 personality modes, conversation history window |
| `pipeline/tts.py` | Dual backend (EdgeTTS with MP3→PCM transcode via miniaudio, CosyVoice direct PCM), auto-fallback |
| `emotion.py` | Regex extraction of `[mood:xxx]` tags, 8 mood enum values: happy, sad, thinking, angry, sleepy, surprised, tsundere, neutral |
| `sensor.py` | Sensor data caching, LLM context generation, threshold alerts with debounce |
| `memory/store.py` | JSON file persistence per user (`data/memory/{user_id}.json`), atomic writes, change detection, sync throttle |
| `care/scheduler.py` | APScheduler 3.x async jobs (sedentary/morning/evening), weather API, conflict-aware push |
| `smarthome/mqtt.py` | aiomqtt wrapper, scene automation (sleep/wakeup), command forwarding |
| `wakeword.py` | openWakeWord for wake word secondary confirmation (2s timeout) |
| `vision.py` | Optional OV7670 capture → LLM multimodal analysis |
| `app.py` | FastAPI factory with lifespan (init order: Config→Log→ASR→LLM→TTS→MQTT→Scheduler→Sessions) |

Full architecture spec: `server/architecture.md`

## Commands

All server commands run from `server/` directory with the venv at `server/.venv/`.

```bash
# Activate venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# Install dependencies (including dev)
pip install -e ".[dev]"

# Run all unit + integration tests (CI-safe)
python -m pytest tests/unit tests/integration -v

# Run a single test file
python -m pytest tests/unit/test_llm.py -v

# Run a single test class or method
python -m pytest tests/unit/test_llm.py::TestSystemPrompt::test_contains_personality -v

# Run with coverage
python -m pytest tests/unit tests/integration --cov=wallace --cov-report=term-missing

# Check coverage threshold (must be ≥80%)
python -m pytest tests/unit tests/integration --cov=wallace --cov-fail-under=80 -q

# E2E tests (requires Ollama running locally, skipped in CI)
python -m pytest tests/e2e -v

# Lint
ruff check wallace/ tests/

# Start server
uvicorn wallace.app:create_app --factory --host 0.0.0.0 --port 8000
```

## CI/CD

GitHub Actions workflow (`.github/workflows/server-test.yml`) runs on every push/PR to `server/`:

1. Tests on Python 3.11 and 3.12 (ubuntu-latest)
2. Steps: Install deps → Lint (ruff) → Unit+Integration tests → Coverage check (≥80%)
3. E2E tests are skipped in CI (require local Ollama)

## Configuration

Main config: `server/config/default.toml`

Key sections:
- `[server]` — host, port, log_level
- `[asr]` — model (large-v3-turbo), device (cuda/cpu), vad_threshold
- `[llm]` — base_url (Ollama), model (deepseek-r1:8b), temperature, max_history_turns
- `[tts]` — default_backend (edge/cosyvoice), voice names
- `[mqtt]` — broker, topic_prefix
- `[care]` — sedentary_interval_hours, morning/evening times
- `[sensor]` — alert thresholds, cooldown

Environment variable override: `WALLACE_SECTION__KEY=value` (e.g., `WALLACE_LLM__MODEL=llama3`)

## Test Structure

```
tests/
├── conftest.py                # Shared fixtures (MockWebSocket, test_config, Session)
├── unit/                      # Mock all external dependencies
│   ├── test_config.py        # Configuration loading
│   ├── test_protocol.py      # WebSocket message serialization
│   ├── test_session.py       # Session state machine
│   ├── test_asr.py           # Speech recognition
│   ├── test_llm.py           # LLM client, personality
│   ├── test_tts.py           # TTS backends
│   ├── test_emotion.py       # Mood tag parsing
│   ├── test_sensor.py        # Sensor data, alerts
│   ├── test_memory.py        # User memory persistence
│   ├── test_wakeword.py      # Wake word verification
│   ├── test_care.py          # Care scheduler
│   └── test_mqtt.py          # MQTT commands
├── integration/              # Module cooperation tests
│   ├── test_orchestrator.py  # Full ASR→LLM→TTS pipeline
│   ├── test_ws_handler.py    # WebSocket routing
│   └── test_care_push.py     # Care + Sensor chain
└── e2e/                      # End-to-end (require Ollama)
    ├── test_ws_e2e.py        # WebSocket full flow
    ├── test_conversation.py  # Multi-turn dialogue
    ├── test_interrupt.py     # Interruption handling
    ├── test_sensor_care.py   # Sensor alerts
    ├── test_reconnect.py     # Connection recovery
    ├── test_memory.py        # Memory across sessions
    ├── test_events.py        # Event handling
    └── test_wakeword.py      # Wake word pipeline
```

## Dependencies

**Python 3.11+ required**

Core:
- `fastapi`, `uvicorn`, `websockets` — Web framework
- `faster-whisper`, `ctranslate2` — Speech recognition
- `httpx` — Ollama/weather API client
- `edge-tts`, `miniaudio` — TTS synthesis + MP3→PCM
- `pydantic-settings` — Configuration
- `aiomqtt` — Smart home
- `apscheduler>=3.10,<4.0` — Scheduled tasks
- `numpy` — Audio processing

Dev:
- `pytest`, `pytest-asyncio`, `pytest-cov` — Testing
- `pytest-httpx` — HTTP mocking
- `pytest-timeout`, `freezegun` — Test utilities
- `ruff` — Linting

Optional:
- `openwakeword` — Wake word verification

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

## Code Conventions

- **Async-first**: All I/O operations use async/await; blocking calls wrapped in `asyncio.to_thread()`
- **Type hints**: All function signatures include type annotations
- **Pydantic models**: Used for config, WebSocket messages, and data validation
- **Error handling**: External service failures (Ollama, edge-tts, MQTT) degrade gracefully without crashing
- **Logging**: Use `logging` module; level configured via `[server].log_level`
- **Line length**: 100 characters max (ruff enforced)

## WebSocket Protocol Summary

**Audio format**: PCM 16kHz 16bit mono little-endian, 1024 bytes per frame

**ESP32 → Server**: `ping`, `audio_start`, `audio_end`, `sensor`, `proximity`, `device_state`, `event`, `wakeword_verify`, `local_cmd`, `image`, `config`

**Server → ESP32**: `pong`, `tts_start`, `tts_end`, `tts_cancel`, `wakeword_result`, `text`, `care`, `command_result`, `memory_sync`, `sensor_alert`, `session_restore`

See `server/architecture.md` for full protocol documentation.

## Language Note

Documentation is written in Chinese (中文).
