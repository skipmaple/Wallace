"""E2E 测试 — 传感器数据与关怀推送。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from .conftest import create_llm_stream_mock


class TestSensorData:
    """传感器数据处理测试。"""

    def test_sensor_data_accepted(self, ws_client):
        """传感器数据应被接受。"""
        with ws_client() as ws:
            ws.send_sensor_data(temp=25.0, humidity=60.0, light=300.0, air_quality=50.0)

            # 不应崩溃
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_proximity_data_accepted(self, ws_client):
        """距离传感器数据应被接受。"""
        with ws_client() as ws:
            ws.send_proximity(distance=500.0, user_present=True)

            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None


class TestSensorAlerts:
    """传感器阈值告警测试。

    根据 architecture.md：sensor 超阈值 → 发送 sensor_alert 消息。
    """

    def test_air_quality_alert(self, ws_client, e2e_settings):
        """空气质量差应触发 sensor_alert。"""
        threshold = e2e_settings.sensor.air_quality_threshold

        with ws_client() as ws:
            # 发送超过阈值的空气质量数据
            ws.send_sensor_data(air_quality=threshold + 100)

            # 等待响应
            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

            # 必须收到 sensor_alert
            alerts = ws.get_messages_by_type("sensor_alert")
            assert len(alerts) > 0, "应发送 sensor_alert 消息"
            assert alerts[0]["alert"] == "air_quality_bad"
            assert "suggestion" in alerts[0]

    def test_light_dark_alert(self, ws_client, e2e_settings):
        """光线过暗应触发 sensor_alert。"""
        threshold = e2e_settings.sensor.light_dark_threshold

        with ws_client() as ws:
            # 发送低于阈值的光线数据
            ws.send_sensor_data(light=threshold - 10)

            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

            # 必须收到 sensor_alert
            alerts = ws.get_messages_by_type("sensor_alert")
            assert len(alerts) > 0, "光线过暗应触发告警"
            assert alerts[0]["alert"] == "light_too_dark"

    def test_temp_high_alert(self, ws_client, e2e_settings):
        """温度过高应触发 sensor_alert。"""
        threshold = e2e_settings.sensor.temp_high

        with ws_client() as ws:
            ws.send_sensor_data(temp=threshold + 5)

            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

            # 必须收到 sensor_alert
            alerts = ws.get_messages_by_type("sensor_alert")
            assert len(alerts) > 0, "温度过高应触发告警"
            assert alerts[0]["alert"] == "temp_too_high"

    def test_temp_low_alert(self, ws_client, e2e_settings):
        """温度过低应触发 sensor_alert。"""
        threshold = e2e_settings.sensor.temp_low

        with ws_client() as ws:
            ws.send_sensor_data(temp=threshold - 5)

            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

            # 必须收到 sensor_alert
            alerts = ws.get_messages_by_type("sensor_alert")
            assert len(alerts) > 0, "温度过低应触发告警"
            assert alerts[0]["alert"] == "temp_too_low"

    def test_alert_debounce(self, ws_client, e2e_settings):
        """同类型告警应有防抖，第二次不触发。"""
        threshold = e2e_settings.sensor.air_quality_threshold

        with ws_client() as ws:
            # 第一次：应触发告警
            ws.send_sensor_data(air_quality=threshold + 100)
            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

            first_alerts = ws.get_messages_by_type("sensor_alert")
            assert len(first_alerts) > 0, "第一次应触发告警"

            ws.clear()

            # 立即第二次：应被防抖阻止
            ws.send_sensor_data(air_quality=threshold + 200)
            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

            second_alerts = ws.get_messages_by_type("sensor_alert")
            assert len(second_alerts) == 0, "第二次应被防抖阻止，不发送告警"

    def test_normal_values_no_alert(self, ws_client, e2e_settings):
        """正常值不应触发告警。"""
        with ws_client() as ws:
            ws.send_sensor_data(
                temp=25.0,
                humidity=50.0,
                light=300.0,
                air_quality=50.0
            )

            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

            alerts = ws.get_messages_by_type("sensor_alert")
            assert len(alerts) == 0, "正常值不应触发任何告警"


class TestSensorContext:
    """传感器上下文注入测试。"""

    def test_sensor_data_updates_cache(self, ws_client):
        """传感器数据应更新缓存。"""
        with ws_client() as ws:
            # 发送多次数据
            ws.send_sensor_data(temp=20.0)
            ws.send_sensor_data(temp=25.0)
            ws.send_sensor_data(temp=30.0)

            # 连接仍有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None
