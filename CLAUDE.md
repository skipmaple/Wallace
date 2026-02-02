# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wallace is an anthropomorphic desktop AI robot with listening, speaking, seeing, sensing, and emotion capabilities. It combines an ESP32-S3 microcontroller with a PC server to create a personified AI companion device. The project is GPLv3 licensed.

## Architecture

**Two-tier system:**
- **ESP32-S3 (N32R16V)**: Handles hardware I/O — microphone (INMP441/I2S), speaker (MAX98357A/I2S), round LCD eye display (GC9A01/SPI), sensors (DHT20, BH1750, VL53L0X, MQ135 over I2C/analog), touch input (TTP223), RGB LED (WS2812B)
- **PC Server (Python FastAPI)**: Runs AI pipeline — ASR (Faster-Whisper), LLM (Ollama/DeepSeek/Llama3), TTS (Edge-TTS/Piper/CosyVoice)

**Data flow**: Touch wake → I2S mic capture → WebSocket to PC → ASR → LLM → TTS → WebSocket back → I2S speaker output. LCD displays eye animations reflecting emotional state.

**Key subsystems**: Emotion engine (happy/sad/angry/neutral from conversation analysis), eye tracking (VL53L0X distance sensor), idle animations, smart home integration (MQTT/HTTP).

## Development Environment

- VS Code + PlatformIO for firmware development
- ESP-IDF 5.x with ESP-SR/ESP-ADF components
- Python virtual environment (.venv/) for server-side tooling

## Repository Structure

**Current State:** This repository is in the planning/documentation phase with no implementation code yet.

**Documentation:**

- [doc/spec.md](doc/spec.md) - Current technical specification (v4.2)
- [doc/purchase-list.md](doc/purchase-list.md) - Current BOM with purchase status
- [doc/archive/](doc/archive/) - Historical design documents (v1 → v4.1)

**Future Code Structure** (when implementation begins):

- `firmware/` - ESP32-S3 firmware (PlatformIO project with platformio.ini)
- `server/` - Python FastAPI server for AI pipeline
- `.venv/` - Python virtual environment (already created)

## TDD Rule (MANDATORY)

This project follows **Test-Driven Development**. Tests already exist for all server modules. When implementing or modifying code:

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

Documentation is written in Chinese (中文). README.md is UTF-16 encoded.
