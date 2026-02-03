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
    """传感器告警全链路。

    根据 architecture.md:
    - 传感器告警全链路 | sensor 超阈值 → LLM 生成 → TTS → WebSocket 发送 sensor_alert + 音频
    """

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

    async def test_air_quality_alert_full_pipeline(
        self, sensor, care_scheduler, session, mock_ws
    ):
        """空气质量差 → LLM 生成提醒 → TTS 合成 → WebSocket 发送 sensor_alert + 音频帧。"""
        # 1. 更新传感器数据（空气质量超阈值）
        sensor.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 300.0, "air_quality": 300.0,
        })

        # 2. 检测告警
        alerts = sensor.check_alerts(session)
        assert len(alerts) > 0, "应检测到空气质量告警"

        # 3. 对每个告警触发 LLM 生成 + TTS + WebSocket 推送
        for alert_type, suggestion in alerts:
            # 使用 care_scheduler 的推送机制
            prompt = f"用户环境告警: {alert_type}。建议: {suggestion}"
            await care_scheduler._push_to_session(session, prompt, "caring")

        # 4. 验证 WebSocket 收到消息
        sent = mock_ws.get_sent_json_messages()

        # 应有 care 消息（告警通过 care 消息推送）
        care_msgs = [m for m in sent if m.get("type") == "care"]
        assert len(care_msgs) >= 1, "应发送告警消息"
        assert care_msgs[0]["content"], "消息应有内容"
        assert care_msgs[0]["mood"], "消息应有情绪"

        # 5. 验证有 TTS 音频帧
        assert len(mock_ws.sent_bytes) > 0, "应发送 TTS 音频帧"

    async def test_light_dark_alert_pipeline(self, sensor, session):
        """光线暗 → 触发告警。"""
        sensor.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 10.0, "air_quality": 100.0,  # 光线很暗
        })
        alerts = sensor.check_alerts(session)
        # 应触发光线暗告警
        light_alerts = [a for a in alerts if "light" in a[0]]
        assert len(light_alerts) > 0, "光线暗应触发告警"
        assert light_alerts[0][1], "应有开灯建议"

    async def test_temperature_alert_pipeline(self, sensor, session):
        """温度异常 → 触发告警。"""
        # 测试高温
        sensor.update_cache(session, {
            "temp": 40.0, "humidity": 60.0, "light": 300.0, "air_quality": 100.0,  # 温度过高
        })
        alerts = sensor.check_alerts(session)
        temp_alerts = [a for a in alerts if "temp" in a[0]]
        assert len(temp_alerts) > 0, "高温应触发告警"

    async def test_alert_debounce(self, session, mock_ws):
        """告警防抖：同类型告警在 cooldown 期内不重复触发。"""
        sensor_with_cooldown = SensorProcessor(SensorConfig(alert_cooldown=300))

        # 第一次告警
        sensor_with_cooldown.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 300.0, "air_quality": 300.0,
        })
        alerts1 = sensor_with_cooldown.check_alerts(session)
        assert len(alerts1) > 0, "第一次应触发告警"

        # 立即再次检测（在 cooldown 期内）
        alerts2 = sensor_with_cooldown.check_alerts(session)
        assert len(alerts2) == 0, "cooldown 期内不应重复触发同类型告警"
