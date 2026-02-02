"""集成测试 — 关怀推送全链路、传感器告警全链路。"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from wallace.config import CareConfig, SensorConfig, WeatherConfig
from wallace.care.scheduler import CareScheduler
from wallace.sensor import SensorProcessor


@pytest.fixture
def sensor():
    return SensorProcessor(SensorConfig(alert_cooldown=0))


@pytest.fixture
def care_scheduler(session, mock_llm, mock_tts):
    sessions = {session.user_id: session}
    return CareScheduler(
        CareConfig(push_timeout=5),
        WeatherConfig(),
        sessions,
        mock_llm,
        mock_tts,
    )


class TestCareFullPipeline:
    """关怀推送全链路。"""

    async def test_scheduler_to_tts_to_ws(self, care_scheduler, session, mock_ws):
        """scheduler 触发 → LLM 生成 → TTS 合成 → WebSocket 发送。"""
        await care_scheduler._sedentary_reminder()

        sent = mock_ws.get_sent_json_messages()
        care_msgs = [m for m in sent if m.get("type") == "care"]
        assert len(care_msgs) >= 1
        assert care_msgs[0]["content"]  # 有文本
        assert care_msgs[0]["mood"]  # 有情绪

        # 有 TTS 音频帧
        assert len(mock_ws.sent_bytes) > 0


class TestSensorAlertFullPipeline:
    """传感器告警全链路。"""

    async def test_sensor_alert_triggers_push(self, sensor, session, mock_ws):
        """传感器超阈值 → check_alerts 返回告警。"""
        sensor.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 300.0, "air_quality": 300.0,
        })
        alerts = sensor.check_alerts(session)
        assert len(alerts) > 0
        alert_type, suggestion = alerts[0]
        assert "air_quality" in alert_type
        assert suggestion  # 有建议文本
