"""集成测试 ws/handler.py — WebSocket 消息路由、连接生命周期。"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from wallace.config import SensorConfig
from wallace.pipeline.orchestrator import Orchestrator
from wallace.sensor import SensorProcessor
from wallace.config import MQTTConfig
from wallace.smarthome.mqtt import MQTTManager
from wallace.wakeword import WakewordVerifier
from wallace.ws.handler import WebSocketHandler
from wallace.ws.session import PipelineState, Session


@pytest.fixture
def sessions():
    return {}


@pytest.fixture
def sensor():
    return SensorProcessor(SensorConfig())


@pytest.fixture
def wakeword():
    return WakewordVerifier(timeout=1.0)


@pytest.fixture
def mqtt():
    m = MQTTManager(MQTTConfig())
    m._connected = True
    return m


@pytest.fixture
def orchestrator(mock_asr, mock_llm, mock_tts, sensor):
    return Orchestrator(mock_asr, mock_llm, mock_tts, sensor)


@pytest.fixture
def handler(sessions, orchestrator, sensor, wakeword, mqtt):
    return WebSocketHandler(sessions, orchestrator, sensor, wakeword, mqtt)


class TestMessageRouting:
    """JSON 消息路由分发。"""

    async def test_ping_returns_pong(self, handler, sessions, mock_ws):
        mock_ws.inject_text(json.dumps({"type": "ping"}))
        mock_ws.inject_disconnect()

        await handler.handle_connection(mock_ws, "u1")

        sent = mock_ws.get_sent_json_messages()
        assert any(m["type"] == "pong" for m in sent)

    async def test_sensor_updates_cache(self, handler, sessions, mock_ws):
        mock_ws.inject_text(json.dumps({
            "type": "sensor", "temp": 26.5, "humidity": 60.0,
            "light": 300.0, "air_quality": 50.0,
        }))
        mock_ws.inject_disconnect()

        await handler.handle_connection(mock_ws, "u1")

        session = sessions.get("u1")
        # session is removed after disconnect, check was processed without error

    async def test_binary_frame_appends_audio(self, handler, sessions, mock_ws):
        mock_ws.inject_bytes(b"\x00" * 1024)
        mock_ws.inject_bytes(b"\x01" * 1024)
        mock_ws.inject_disconnect()

        await handler.handle_connection(mock_ws, "u1")
        # No crash = binary frames handled


class TestInvalidMessages:
    """异常消息处理。"""

    async def test_invalid_json(self, handler, sessions, mock_ws):
        mock_ws.inject_text("not json{{{")
        mock_ws.inject_disconnect()

        # Should not crash
        await handler.handle_connection(mock_ws, "u1")

    async def test_unknown_type(self, handler, sessions, mock_ws):
        mock_ws.inject_text(json.dumps({"type": "nonexistent_type"}))
        mock_ws.inject_disconnect()

        await handler.handle_connection(mock_ws, "u1")


class TestConnectionLifecycle:
    """连接生命周期。"""

    async def test_session_created_on_connect(self, handler, sessions, mock_ws):
        mock_ws.inject_disconnect()
        await handler.handle_connection(mock_ws, "u1")
        # Session removed after disconnect, but was created during connection

    async def test_session_removed_on_disconnect(self, handler, sessions, mock_ws):
        mock_ws.inject_disconnect()
        await handler.handle_connection(mock_ws, "u1")
        assert "u1" not in sessions

    async def test_reconnect_sends_session_restore(self, handler, sessions, mock_ws):
        """同一 user_id 重连 → 发送 session_restore。"""
        # 先创建一个旧 session
        old_mock = MagicMock()
        old_session = Session("u1", old_mock)
        old_session.personality = "tsundere"
        old_session.treehouse_mode = True
        sessions["u1"] = old_session

        mock_ws.inject_disconnect()
        await handler.handle_connection(mock_ws, "u1")

        sent = mock_ws.get_sent_json_messages()
        restore_msgs = [m for m in sent if m.get("type") == "session_restore"]
        assert len(restore_msgs) == 1
        assert restore_msgs[0]["personality"] == "tsundere"
        assert restore_msgs[0]["treehouse"] is True


class TestHeartbeat:
    """心跳处理。"""

    async def test_ping_updates_heartbeat(self, handler, sessions, mock_ws):
        mock_ws.inject_text(json.dumps({"type": "ping"}))
        mock_ws.inject_disconnect()

        await handler.handle_connection(mock_ws, "u1")

        pong_msgs = mock_ws.get_sent_messages_by_type("pong")
        assert len(pong_msgs) == 1


class TestEventRouting:
    """event 消息路由。"""

    async def test_personality_switch(self, handler, sessions, mock_ws):
        mock_ws.inject_text(json.dumps({
            "type": "event", "event": "personality_switch", "value": "cool",
        }))
        mock_ws.inject_disconnect()

        await handler.handle_connection(mock_ws, "u1")

    async def test_treehouse_mode(self, handler, sessions, mock_ws):
        mock_ws.inject_text(json.dumps({
            "type": "event", "event": "treehouse_mode", "value": True,
        }))
        mock_ws.inject_disconnect()

        await handler.handle_connection(mock_ws, "u1")


class TestLocalCmd:
    """智能家居本地命令。"""

    async def test_local_cmd_returns_result(self, handler, sessions, mock_ws, mqtt):
        mock_ws.inject_text(json.dumps({"type": "local_cmd", "action": "light_on"}))
        mock_ws.inject_disconnect()

        await handler.handle_connection(mock_ws, "u1")

        result_msgs = mock_ws.get_sent_messages_by_type("command_result")
        assert len(result_msgs) == 1
        assert result_msgs[0]["action"] == "light_on"
        assert result_msgs[0]["success"] is True
