"""测试 smarthome/mqtt.py — MQTT 转发、场景联动、断连。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wallace.config import MQTTConfig
from wallace.smarthome.mqtt import SCENES, MQTTManager


@pytest.fixture
def mqtt_config() -> MQTTConfig:
    return MQTTConfig(topic_prefix="wallace/test")


@pytest.fixture
def mqtt_manager(mqtt_config) -> MQTTManager:
    return MQTTManager(mqtt_config)


class TestExecuteCommand:
    """单个命令执行。"""

    async def test_execute_when_connected(self, mqtt_manager):
        mqtt_manager._connected = True
        success, msg = await mqtt_manager.execute_command("light_on")
        assert success is True

    async def test_execute_when_disconnected(self, mqtt_manager):
        mqtt_manager._connected = False
        success, msg = await mqtt_manager.execute_command("light_on")
        assert success is False
        assert "not connected" in msg.lower()


class TestScenes:
    """场景联动。"""

    def test_sleep_scene_defined(self):
        assert "sleep" in SCENES
        assert len(SCENES["sleep"]) >= 2

    def test_wakeup_scene_defined(self):
        assert "wakeup" in SCENES

    async def test_execute_scene_sleep(self, mqtt_manager):
        mqtt_manager._connected = True
        results = await mqtt_manager.execute_scene("sleep")
        assert len(results) >= 2
        assert all(r[1] for r in results)  # all success

    async def test_unknown_scene(self, mqtt_manager):
        mqtt_manager._connected = True
        results = await mqtt_manager.execute_scene("nonexistent")
        assert len(results) == 1
        assert results[0][1] is False


class TestConnection:
    """连接管理。"""

    async def test_connect_failure_degrades(self, mqtt_manager):
        """MQTT broker 不可用 → 降级模式。"""
        with patch("wallace.smarthome.mqtt.aiomqtt") as mock_aiomqtt:
            mock_aiomqtt.Client.side_effect = Exception("Connection refused")
            await mqtt_manager.connect()
        assert mqtt_manager.is_connected is False

    async def test_disconnect(self, mqtt_manager):
        mqtt_manager._connected = True
        await mqtt_manager.disconnect()
        assert mqtt_manager.is_connected is False

    def test_topic_format(self, mqtt_manager):
        """Topic 格式正确。"""
        prefix = mqtt_manager.config.topic_prefix
        topic = f"{prefix}/light_on"
        assert topic == "wallace/test/light_on"
