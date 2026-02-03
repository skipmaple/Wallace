"""E2E 测试专用 fixtures — mock 外部服务，使用 TestClient。"""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from wallace.config import Settings, load_settings
from wallace.ws.session import UserMemory

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ────────────────────── E2E WebSocket Client ──────────────────────


class E2EWebSocketClient:
    """E2E 测试 WebSocket 客户端辅助类。"""

    def __init__(self, websocket) -> None:
        self.ws = websocket
        self.received_json: list[dict] = []
        self.received_bytes: list[bytes] = []

    def send_json(self, data: dict) -> None:
        """发送 JSON 消息。"""
        self.ws.send_json(data)

    def send_bytes(self, data: bytes) -> None:
        """发送二进制消息。"""
        self.ws.send_bytes(data)

    def send_ping(self) -> None:
        """发送心跳。"""
        self.send_json({"type": "ping"})

    def send_audio_start(self) -> None:
        """发送音频开始信号。"""
        self.send_json({"type": "audio_start"})

    def send_audio_end(self) -> None:
        """发送音频结束信号。"""
        self.send_json({"type": "audio_end"})

    def send_audio_frames(self, frames: list[bytes]) -> None:
        """发送多帧音频数据。"""
        for frame in frames:
            self.send_bytes(frame)

    def send_sensor_data(
        self,
        temp: float = 25.0,
        humidity: float = 60.0,
        light: float = 300.0,
        air_quality: float = 50.0,
    ) -> None:
        """发送传感器数据。"""
        self.send_json({
            "type": "sensor",
            "temp": temp,
            "humidity": humidity,
            "light": light,
            "air_quality": air_quality,
        })

    def send_proximity(self, distance: float, user_present: bool = True) -> None:
        """发送距离传感器数据。"""
        self.send_json({
            "type": "proximity",
            "distance": distance,
            "user_present": user_present,
        })

    def send_event(self, event: str, value: Any) -> None:
        """发送事件消息。"""
        self.send_json({"type": "event", "event": event, "value": value})

    def send_local_cmd(self, action: str) -> None:
        """发送本地命令。"""
        self.send_json({"type": "local_cmd", "action": action})

    def receive_json_msg(self) -> dict:
        """接收一条 JSON 消息。"""
        data = self.ws.receive_json()
        self.received_json.append(data)
        return data

    def receive_bytes_msg(self) -> bytes:
        """接收一条二进制消息。"""
        data = self.ws.receive_bytes()
        self.received_bytes.append(data)
        return data

    def receive_one(self) -> dict | bytes:
        """接收一条消息（自动检测类型）。"""
        # Starlette TestClient 不支持直接判断消息类型
        # 先尝试 JSON，失败则尝试 bytes
        try:
            return self.receive_json_msg()
        except Exception:
            return self.receive_bytes_msg()

    def receive_until_type(
        self, target_type: str, max_messages: int = 100
    ) -> tuple[list[dict], list[bytes]]:
        """接收消息直到收到指定类型（找到后立即返回）。

        使用 receive_json() 直接接收 JSON 消息，遇到二进制则捕获异常。
        """
        json_msgs: list[dict] = []
        binary_msgs: list[bytes] = []

        for _ in range(max_messages):
            try:
                # 直接使用 receive_json()，Starlette TestClient 支持
                msg = self.ws.receive_json()
                json_msgs.append(msg)
                self.received_json.append(msg)
                if msg.get("type") == target_type:
                    return json_msgs, binary_msgs  # 立即返回
            except Exception:
                # 可能是二进制消息或连接关闭
                try:
                    data = self.ws.receive_bytes()
                    binary_msgs.append(data)
                    self.received_bytes.append(data)
                except Exception:
                    break

        return json_msgs, binary_msgs

    def receive_all_available(
        self, timeout: float = 1.0, max_messages: int = 50
    ) -> tuple[list[dict], list[bytes]]:
        """接收消息直到收到 tts_end。

        注意：Starlette TestClient 的 receive() 是阻塞的，
        timeout 参数仅为兼容性保留。
        """
        return self.receive_until_type("tts_end", max_messages=max_messages)

    def verify_no_tts_response(self) -> None:
        """验证没有 TTS 响应：发送 ping 并检查是否有 tts_start。

        用于测试期望无响应的场景（如 VAD 无语音、ASR 空文本）。
        """
        self.send_ping()
        # 等待 pong，同时收集之前可能的 tts_start
        pong = self.wait_for_message_type("pong", timeout=2.0)
        assert pong is not None, "Connection should still be valid"
        # 检查是否收到了 tts_start（不应该有）
        assert "tts_start" not in self.get_message_sequence(), \
            "Should not have TTS response"
        assert len(self.received_bytes) == 0, "Should not have binary frames"

    def wait_for_message_type(
        self, msg_type: str, timeout: float = 5.0, max_messages: int = 50
    ) -> dict | None:
        """等待特定类型的消息。

        timeout 参数仅为兼容性保留。
        """
        json_msgs, _ = self.receive_until_type(msg_type, max_messages)
        for msg in json_msgs:
            if msg.get("type") == msg_type:
                return msg
        return None

    def get_message_sequence(self) -> list[str]:
        """获取接收到的消息类型序列。"""
        return [m.get("type") for m in self.received_json]

    def get_messages_by_type(self, msg_type: str) -> list[dict]:
        """获取指定类型的所有消息。"""
        return [m for m in self.received_json if m.get("type") == msg_type]

    def clear(self) -> None:
        """清空已接收的消息。"""
        self.received_json.clear()
        self.received_bytes.clear()


# ────────────────────── Mock Factories ──────────────────────


def create_llm_stream_mock(
    tokens: list[str],
    delay: float = 0.0,
) -> Callable:
    """创建可控的 LLM 流式输出 mock。"""
    async def stream(messages):
        for token in tokens:
            if delay > 0:
                await asyncio.sleep(delay)
            yield token
    return stream


def create_tts_mock(
    frame_count: int = 2,
    frame_size: int = 1024,
    frame_delay: float = 0.0,
) -> Callable:
    """创建可控的 TTS 合成 mock。"""
    async def synthesize(text):
        for _ in range(frame_count):
            if frame_delay > 0:
                await asyncio.sleep(frame_delay)
            yield b"\x00" * frame_size
    return synthesize


# ────────────────────── Assertion Helpers ──────────────────────


def assert_message_sequence(received: list[dict], expected_order: list[str]) -> None:
    """断言消息类型按预期顺序出现。"""
    types = [m.get("type") for m in received]
    indices = []
    for expected in expected_order:
        try:
            # 从上一个位置之后查找
            start = indices[-1] + 1 if indices else 0
            idx = types.index(expected, start)
            indices.append(idx)
        except ValueError:
            raise AssertionError(
                f"Expected message type '{expected}' not found after position {start} in {types}"
            )


def assert_has_binary_frames(received_bytes: list[bytes], min_count: int = 1) -> None:
    """断言至少收到 min_count 个二进制帧。"""
    assert len(received_bytes) >= min_count, \
        f"Expected at least {min_count} binary frames, got {len(received_bytes)}"


def assert_message_contains(msg: dict, **expected_fields) -> None:
    """断言消息包含预期字段。"""
    for key, value in expected_fields.items():
        assert key in msg, f"Message missing field '{key}': {msg}"
        assert msg[key] == value, f"Field '{key}' expected {value}, got {msg[key]}"


# ────────────────────── Fixtures ──────────────────────


@pytest.fixture
def e2e_settings() -> Settings:
    """加载 E2E 测试配置。"""
    return load_settings(FIXTURES_DIR / "test_config.toml")


@pytest.fixture
def mock_asr_engine() -> MagicMock:
    """Mock ASREngine — 返回可控转录结果。"""
    engine = MagicMock()
    engine.load_model = AsyncMock()
    engine.transcribe = AsyncMock(return_value="你好华莱士")
    engine.vad_has_speech = MagicMock(return_value=True)
    return engine


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Mock LLMClient — 返回可控流式输出。"""
    client = MagicMock()
    client.start = AsyncMock()
    client.close = AsyncMock()
    client.is_healthy = True
    client.health_check = AsyncMock(return_value=True)
    client.build_messages = MagicMock(return_value=[
        {"role": "system", "content": "你是 Wallace"},
        {"role": "user", "content": "test"},
    ])
    client.chat_stream = create_llm_stream_mock(["你好", "呀！", "[mood:happy]"])
    client.switch_personality = MagicMock()
    return client


@pytest.fixture
def mock_tts_manager() -> MagicMock:
    """Mock TTSManager — 返回可控 PCM 帧。"""
    manager = MagicMock()
    manager.current_backend = "edge"
    manager.switch_backend = MagicMock()
    manager.synthesize = create_tts_mock(frame_count=2)
    return manager


@pytest.fixture
def mock_mqtt_manager() -> MagicMock:
    """Mock MQTTManager。"""
    manager = MagicMock()
    manager.is_connected = True
    manager.connect = AsyncMock()
    manager.disconnect = AsyncMock()
    manager.execute_command = AsyncMock(return_value=(True, "executed"))
    manager.execute_scene = AsyncMock(return_value=[("light/off", True, "ok")])
    return manager


@pytest.fixture
def mock_care_scheduler() -> MagicMock:
    """Mock CareScheduler — 禁用定时任务。"""
    scheduler = MagicMock()
    scheduler.start = AsyncMock()
    scheduler.stop = AsyncMock()
    return scheduler


@pytest.fixture
def mock_sensor_processor(e2e_settings) -> MagicMock:
    """Mock SensorProcessor。"""
    from wallace.sensor import SensorProcessor
    processor = SensorProcessor(e2e_settings.sensor)
    return processor


@pytest.fixture
def mock_wakeword() -> MagicMock:
    """Mock WakewordVerifier。"""
    verifier = MagicMock()
    verifier.verify = AsyncMock(return_value=True)
    return verifier


@pytest.fixture
def mock_orchestrator(
    mock_asr_engine,
    mock_llm_client,
    mock_tts_manager,
    mock_sensor_processor,
) -> MagicMock:
    """Mock Orchestrator — 用于直接测试。"""
    from wallace.pipeline.orchestrator import Orchestrator
    return Orchestrator(
        mock_asr_engine,
        mock_llm_client,
        mock_tts_manager,
        mock_sensor_processor,
    )


@pytest.fixture
def e2e_app_and_client(
    e2e_settings,
    mock_asr_engine,
    mock_llm_client,
    mock_tts_manager,
    mock_mqtt_manager,
    mock_care_scheduler,
    mock_wakeword,
):
    """创建带有 mock 组件的 FastAPI 应用和 TestClient。

    将 patch、app 创建和 TestClient 合并到一个 fixture 中，
    确保 patches 在整个测试期间保持有效。
    """
    from wallace.app import create_app

    with patch("wallace.app.ASREngine") as MockASR, \
         patch("wallace.app.LLMClient") as MockLLM, \
         patch("wallace.app.TTSManager") as MockTTS, \
         patch("wallace.app.MQTTManager") as MockMQTT, \
         patch("wallace.app.CareScheduler") as MockCare, \
         patch("wallace.app.WakewordVerifier") as MockWakeword:

        MockASR.return_value = mock_asr_engine
        MockLLM.return_value = mock_llm_client
        MockTTS.return_value = mock_tts_manager
        MockMQTT.return_value = mock_mqtt_manager
        MockCare.return_value = mock_care_scheduler
        MockWakeword.return_value = mock_wakeword

        app = create_app(e2e_settings)

        # 确保 mock 对象被正确引用
        app.state._mock_asr = mock_asr_engine
        app.state._mock_llm = mock_llm_client
        app.state._mock_tts = mock_tts_manager
        app.state._mock_mqtt = mock_mqtt_manager
        app.state._mock_wakeword = mock_wakeword

        with TestClient(app) as client:
            yield app, client


@pytest.fixture
def e2e_app(e2e_app_and_client):
    """获取 FastAPI 应用。"""
    app, _ = e2e_app_and_client
    return app


@pytest.fixture
def client(e2e_app_and_client) -> TestClient:
    """获取 TestClient。"""
    _, client = e2e_app_and_client
    return client


@pytest.fixture
def ws_client(e2e_app_and_client):
    """创建 WebSocket 客户端工厂。"""
    _, client = e2e_app_and_client

    @contextmanager
    def _connect(user_id: str = "test_user"):
        with client.websocket_connect(f"/ws/{user_id}") as ws:
            yield E2EWebSocketClient(ws)
    return _connect
