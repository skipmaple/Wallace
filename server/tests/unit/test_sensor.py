"""测试 sensor.py — 传感器缓存、上下文生成、阈值告警、防抖。"""

from __future__ import annotations


import pytest

from wallace.config import SensorConfig
from wallace.sensor import SensorProcessor


@pytest.fixture
def sensor_config() -> SensorConfig:
    return SensorConfig(
        alert_cooldown=10,  # 10 秒便于测试
        air_quality_threshold=200,
        light_dark_threshold=50,
        temp_high=35,
        temp_low=10,
    )


@pytest.fixture
def sensor(sensor_config) -> SensorProcessor:
    return SensorProcessor(sensor_config)


class TestCacheUpdate:
    """传感器数据缓存。"""

    def test_update_all_fields(self, sensor, session):
        sensor.update_cache(session, {
            "temp": 26.5, "humidity": 60.0, "light": 300.0, "air_quality": 50.0
        })
        assert session.sensor_cache.temp == 26.5
        assert session.sensor_cache.humidity == 60.0
        assert session.sensor_cache.light == 300.0
        assert session.sensor_cache.air_quality == 50.0
        assert session.sensor_cache.updated_at > 0

    def test_partial_update(self, sensor, session):
        sensor.update_cache(session, {"temp": 20.0})
        assert session.sensor_cache.temp == 20.0
        assert session.sensor_cache.humidity == 0.0  # default

    def test_proximity_update(self, sensor, session):
        sensor.update_proximity(session, {"user_present": False, "distance": 500.0})
        assert session.proximity_present is False

    def test_proximity_default(self, session):
        """未收到 proximity 消息时使用默认值。"""
        assert session.proximity_present is True


class TestLLMContext:
    """LLM 上下文生成。"""

    def test_no_data_returns_empty(self, sensor, session):
        assert sensor.build_llm_context(session) == ""

    def test_with_data(self, sensor, session):
        sensor.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 300.0, "air_quality": 50.0
        })
        ctx = sensor.build_llm_context(session)
        assert "室温26°C" in ctx
        assert "湿度60%" in ctx
        assert "当前环境" in ctx

    def test_dark_light_description(self, sensor, session):
        sensor.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 10.0, "air_quality": 50.0
        })
        ctx = sensor.build_llm_context(session)
        assert "光线较暗" in ctx

    def test_bad_air_description(self, sensor, session):
        sensor.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 300.0, "air_quality": 300.0
        })
        ctx = sensor.build_llm_context(session)
        assert "空气质量较差" in ctx


class TestAlerts:
    """阈值告警。"""

    def test_air_quality_alert(self, sensor, session):
        sensor.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 300.0, "air_quality": 300.0
        })
        alerts = sensor.check_alerts(session)
        types = [a[0] for a in alerts]
        assert "air_quality_bad" in types

    def test_light_dark_alert(self, sensor, session):
        sensor.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 10.0, "air_quality": 50.0
        })
        alerts = sensor.check_alerts(session)
        types = [a[0] for a in alerts]
        assert "light_too_dark" in types

    def test_temp_high_alert(self, sensor, session):
        sensor.update_cache(session, {
            "temp": 40.0, "humidity": 60.0, "light": 300.0, "air_quality": 50.0
        })
        alerts = sensor.check_alerts(session)
        types = [a[0] for a in alerts]
        assert "temp_too_high" in types

    def test_temp_low_alert(self, sensor, session):
        sensor.update_cache(session, {
            "temp": 5.0, "humidity": 60.0, "light": 300.0, "air_quality": 50.0
        })
        alerts = sensor.check_alerts(session)
        types = [a[0] for a in alerts]
        assert "temp_too_low" in types

    def test_no_alert_normal_values(self, sensor, session):
        sensor.update_cache(session, {
            "temp": 25.0, "humidity": 60.0, "light": 300.0, "air_quality": 50.0
        })
        alerts = sensor.check_alerts(session)
        assert alerts == []


class TestAlertDebounce:
    """告警防抖。"""

    def test_debounce_blocks_second_alert(self, sensor, session):
        sensor.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 300.0, "air_quality": 300.0
        })
        alerts1 = sensor.check_alerts(session)
        assert len(alerts1) > 0

        # 立即再次检查 → 被防抖阻止
        alerts2 = sensor.check_alerts(session)
        assert len(alerts2) == 0

    def test_debounce_expires(self, sensor_config, session):
        # 使用极短 cooldown
        sensor_config.alert_cooldown = 0  # 0 秒，立即过期
        sensor_proc = SensorProcessor(sensor_config)

        sensor_proc.update_cache(session, {
            "temp": 26.0, "humidity": 60.0, "light": 300.0, "air_quality": 300.0
        })
        alerts1 = sensor_proc.check_alerts(session)
        assert len(alerts1) > 0

        # cooldown = 0，再次检查应立即通过
        alerts2 = sensor_proc.check_alerts(session)
        assert len(alerts2) > 0
