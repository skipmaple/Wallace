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


class TestReconnection:
    """断连重连测试。

    根据 architecture.md §smarthome/mqtt.py:
    - aiomqtt 客户端（需处理断线重连：捕获 MqttError 后重建 Client 实例并重新订阅）
    """

    @pytest.mark.xfail(reason="MQTT 自动重连功能尚未实现")
    async def test_auto_reconnect_after_disconnect(self, mqtt_manager):
        """断连后自动重连。"""
        mqtt_manager._connected = True

        # 模拟断连
        with patch("wallace.smarthome.mqtt.aiomqtt") as mock_aiomqtt:
            # 第一次调用抛异常（断连），第二次成功
            mock_client = MagicMock()
            mock_aiomqtt.Client.side_effect = [Exception("Connection lost"), mock_client]

            # 执行命令触发断连检测
            success, _ = await mqtt_manager.execute_command("light_on")

            # 应自动重连
            assert mqtt_manager.is_connected is True
            assert mock_aiomqtt.Client.call_count >= 2  # 断连后重建 client

    @pytest.mark.xfail(reason="MQTT 自动重连功能尚未实现")
    async def test_reconnect_interval(self, mqtt_config):
        """重连间隔遵循配置。"""
        mqtt_config.reconnect_interval = 1  # 1秒重试
        manager = MQTTManager(mqtt_config)

        # 模拟连续连接失败
        with patch("wallace.smarthome.mqtt.aiomqtt") as mock_aiomqtt:
            mock_aiomqtt.Client.side_effect = Exception("Refused")

            import time
            start = time.time()
            # 尝试重连（应等待 reconnect_interval）
            await manager.connect()
            await manager.connect()  # 第二次尝试
            elapsed = time.time() - start

            # 两次连接尝试间应有间隔
            assert elapsed >= mqtt_config.reconnect_interval


class TestCommandResultCallback:
    """设备状态回传测试。

    根据 architecture.md:
    - 订阅状态反馈 → 通过 command_result 返回 ESP32
    """

    @pytest.mark.xfail(reason="MQTT 状态订阅回调功能尚未实现")
    async def test_subscribe_to_device_status(self, mqtt_manager):
        """订阅设备状态 topic。"""
        mqtt_manager._connected = True

        with patch("wallace.smarthome.mqtt.aiomqtt"):
            mock_client = AsyncMock()
            mqtt_manager._client = mock_client

            # 应订阅状态反馈 topic
            await mqtt_manager.subscribe_status()

            mock_client.subscribe.assert_called()
            # 验证订阅了正确的 topic 模式
            call_args = mock_client.subscribe.call_args
            assert "status" in str(call_args) or "result" in str(call_args)

    @pytest.mark.xfail(reason="MQTT 状态订阅回调功能尚未实现")
    async def test_status_callback_to_session(self, mqtt_manager, mock_ws, session):
        """收到设备状态 → 构造 command_result → 发送到 ESP32。"""
        mqtt_manager._connected = True
        mqtt_manager._sessions = {session.user_id: session}

        # 模拟收到设备状态消息
        status_payload = {"device": "light", "status": "on", "success": True}

        await mqtt_manager._on_status_received("wallace/test/light/status", status_payload)

        # 应发送 command_result 到 WebSocket
        sent = mock_ws.get_sent_json_messages()
        result_msgs = [m for m in sent if m.get("type") == "command_result"]
        assert len(result_msgs) >= 1
        assert result_msgs[0]["success"] is True
