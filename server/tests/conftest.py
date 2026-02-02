"""共享 fixtures — mock WebSocket, 测试配置, Session 等。"""

from __future__ import annotations

import asyncio
import json
import struct
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from wallace.config import Settings, load_settings
from wallace.ws.session import Session, UserMemory

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ────────────────────── Mock WebSocket ──────────────────────


class MockWebSocket:
    """模拟 FastAPI WebSocket，记录发送的消息。"""

    def __init__(self) -> None:
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []
        self._receive_queue: asyncio.Queue = asyncio.Queue()
        self.closed = False

    async def accept(self) -> None:
        pass

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def receive(self) -> dict[str, Any]:
        return await self._receive_queue.get()

    async def close(self, code: int = 1000) -> None:
        self.closed = True

    def inject_text(self, data: str) -> None:
        """注入一条 JSON 文本消息到接收队列。"""
        self._receive_queue.put_nowait({"type": "websocket.receive", "text": data})

    def inject_bytes(self, data: bytes) -> None:
        """注入一条二进制消息到接收队列。"""
        self._receive_queue.put_nowait({"type": "websocket.receive", "bytes": data})

    def inject_disconnect(self) -> None:
        """注入断开事件。"""
        self._receive_queue.put_nowait({"type": "websocket.disconnect"})

    def get_sent_json_messages(self) -> list[dict]:
        """将所有已发送的 JSON 文本解析为 dict 列表。"""
        return [json.loads(t) for t in self.sent_text]

    def get_sent_messages_by_type(self, msg_type: str) -> list[dict]:
        """筛选指定 type 的已发送消息。"""
        return [m for m in self.get_sent_json_messages() if m.get("type") == msg_type]


# ────────────────────── Fixtures ──────────────────────


@pytest.fixture
def test_config() -> Settings:
    """加载测试专用配置。"""
    return load_settings(FIXTURES_DIR / "test_config.toml")


@pytest.fixture
def mock_ws() -> MockWebSocket:
    """创建一个 MockWebSocket 实例。"""
    return MockWebSocket()


@pytest.fixture
def session(mock_ws: MockWebSocket) -> Session:
    """创建一个测试 Session，挂载 mock_ws。"""
    s = Session(user_id="test_user", ws=mock_ws)  # type: ignore[arg-type]
    s.memory = UserMemory(
        nickname="小明",
        preferences=["喜欢听音乐"],
        interests=["编程", "天文"],
        recent_topics=["天气"],
        important_dates={"birthday": "03-15"},
        interaction_count=42,
        first_met="2024-01-01",
    )
    return s


@pytest.fixture
def mock_asr() -> MagicMock:
    """Mock ASR 引擎 — 返回固定转录文本。"""
    asr = MagicMock()
    asr.transcribe = AsyncMock(return_value="你好华莱士")
    asr.vad_has_speech = MagicMock(return_value=True)
    return asr


@pytest.fixture
def mock_llm() -> MagicMock:
    """Mock LLM 客户端。"""
    llm = MagicMock()
    llm.is_healthy = True
    llm.health_check = AsyncMock(return_value=True)
    llm.build_messages = MagicMock(
        return_value=[
            {"role": "system", "content": "test"},
            {"role": "user", "content": "你好"},
        ]
    )

    async def _fake_stream(messages):
        for token in ["你好", "呀！", "[mood:happy]"]:
            yield token

    llm.chat_stream = _fake_stream
    llm.switch_personality = MagicMock()
    return llm


@pytest.fixture
def mock_tts() -> MagicMock:
    """Mock TTS 管理器 — 返回固定 PCM 帧。"""
    tts = MagicMock()
    tts.current_backend = "edge"
    tts.switch_backend = MagicMock()

    async def _fake_synthesize(text):
        # 产出 2 帧 PCM
        yield b"\x00" * 1024
        yield b"\x00" * 1024

    tts.synthesize = _fake_synthesize
    return tts


@pytest.fixture
def mock_mqtt() -> MagicMock:
    """Mock MQTT 管理器。"""
    mqtt = MagicMock()
    mqtt.is_connected = True
    mqtt.connect = AsyncMock()
    mqtt.disconnect = AsyncMock()
    mqtt.execute_command = AsyncMock(return_value=(True, "executed"))
    mqtt.execute_scene = AsyncMock(return_value=[("light/off", True, "ok")])
    return mqtt


@pytest.fixture
def pcm_audio() -> bytes:
    """生成 1 秒测试用 PCM 音频 (16kHz 16bit mono = 32000 bytes)。

    简单正弦波 440Hz。
    """
    sample_rate = 16000
    duration = 1.0
    freq = 440.0
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, endpoint=False)
    wave = (np.sin(2 * np.pi * freq * t) * 16000).astype(np.int16)
    return wave.tobytes()


@pytest.fixture
def silence_audio() -> bytes:
    """1 秒静音 PCM。"""
    return b"\x00" * 32000


@pytest.fixture
def sample_memory_data() -> dict:
    """测试用记忆数据。"""
    return json.loads((FIXTURES_DIR / "memory_sample.json").read_text(encoding="utf-8"))
