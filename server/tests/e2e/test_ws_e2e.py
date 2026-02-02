"""端到端测试 — WebSocket 全链路（需要外部服务）。

标记 @pytest.mark.e2e，CI 中跳过。
"""

from __future__ import annotations

import json

import numpy as np
import pytest

pytestmark = pytest.mark.e2e


class TestWebSocketE2E:
    """WebSocket 端到端测试。

    需要本地启动 Ollama 和 Wallace server。
    这些测试用 FastAPI TestClient 模拟。
    """

    @pytest.fixture
    def app(self, test_config):
        """创建测试用 FastAPI app。"""
        from wallace.app import create_app

        return create_app(test_config)

    async def test_conversation_roundtrip(self, app):
        """连接 → 发音频 → 收到 TTS 回复。"""
        # TODO: 实现（需要 ASR/LLM/TTS 真实或 mock 后端）
        pytest.skip("E2E test requires external services")

    async def test_interrupt_during_playback(self, app):
        """播放中发 audio_start → 收到 tts_cancel。"""
        pytest.skip("E2E test requires external services")

    async def test_multi_turn_conversation(self, app):
        """3 轮对话 → 对话历史正确累积。"""
        pytest.skip("E2E test requires external services")

    async def test_sensor_triggers_alert(self, app):
        """发传感器数据 → 触发告警 → 收到 sensor_alert。"""
        pytest.skip("E2E test requires external services")

    async def test_personality_switch(self, app):
        """发 personality_switch → 后续对话 prompt 更新。"""
        pytest.skip("E2E test requires external services")
