"""测试 protocol.py — 消息序列化/反序列化。"""

from __future__ import annotations

import pytest

from wallace.ws.protocol import (
    AudioEndMessage,
    AudioStartMessage,
    CareMessage,
    CommandResultMessage,
    ConfigMessage,
    DeviceStateMessage,
    EventMessage,
    ImageMessage,
    LocalCmdMessage,
    MemorySyncMessage,
    PingMessage,
    PongMessage,
    ProximityMessage,
    SensorAlertMessage,
    SensorMessage,
    SessionRestoreMessage,
    TTSCancelMessage,
    TTSEndMessage,
    TTSStartMessage,
    TextMessage,
    WakewordResultMessage,
    WakewordVerifyMessage,
    parse_esp32_message,
    parse_server_message,
)


class TestESP32Messages:
    """ESP32 → Server 消息序列化/反序列化。"""

    @pytest.mark.parametrize(
        "cls,data",
        [
            (PingMessage, {"type": "ping"}),
            (AudioStartMessage, {"type": "audio_start"}),
            (AudioEndMessage, {"type": "audio_end"}),
            (
                WakewordVerifyMessage,
                {"type": "wakeword_verify", "audio": "dGVzdA=="},
            ),
            (
                SensorMessage,
                {
                    "type": "sensor",
                    "temp": 26.5,
                    "humidity": 60.0,
                    "light": 300.0,
                    "air_quality": 50.0,
                },
            ),
            (
                ProximityMessage,
                {"type": "proximity", "distance": 120.0, "user_present": True},
            ),
            (
                DeviceStateMessage,
                {
                    "type": "device_state",
                    "battery_pct": 85,
                    "power_mode": "NORMAL",
                    "wifi_rssi": -45,
                },
            ),
            (
                EventMessage,
                {"type": "event", "event": "personality_switch", "value": "tsundere"},
            ),
            (EventMessage, {"type": "event", "event": "shake"}),
            (EventMessage, {"type": "event", "event": "touch"}),
            (
                EventMessage,
                {"type": "event", "event": "treehouse_mode", "value": True},
            ),
            (LocalCmdMessage, {"type": "local_cmd", "action": "light_on"}),
            (ImageMessage, {"type": "image", "data": "base64data"}),
            (ConfigMessage, {"type": "config", "tts_backend": "cosyvoice"}),
        ],
    )
    def test_roundtrip(self, cls, data):
        """序列化 → 反序列化往返一致。"""
        msg = parse_esp32_message(data)
        assert isinstance(msg, cls)
        dumped = msg.model_dump()
        assert dumped["type"] == data["type"]

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown ESP32"):
            parse_esp32_message({"type": "nonexistent"})

    def test_missing_required_field(self):
        """缺少必填字段抛 ValidationError。"""
        with pytest.raises(Exception):
            parse_esp32_message({"type": "sensor", "temp": 26.5})
            # humidity, light, air_quality 缺失


class TestServerMessages:
    """Server → ESP32 消息序列化/反序列化。"""

    @pytest.mark.parametrize(
        "cls,data",
        [
            (WakewordResultMessage, {"type": "wakeword_result", "confirmed": True}),
            (WakewordResultMessage, {"type": "wakeword_result", "confirmed": False}),
            (TTSStartMessage, {"type": "tts_start", "mood": "happy"}),
            (TTSCancelMessage, {"type": "tts_cancel"}),
            (TTSEndMessage, {"type": "tts_end"}),
            (PongMessage, {"type": "pong"}),
            (
                SessionRestoreMessage,
                {
                    "type": "session_restore",
                    "personality": "normal",
                    "treehouse": False,
                    "tts_backend": "edge",
                },
            ),
            (
                TextMessage,
                {
                    "type": "text",
                    "content": "你好",
                    "partial": False,
                    "mood": "happy",
                },
            ),
            (TextMessage, {"type": "text", "content": "你好"}),
            (CareMessage, {"type": "care", "content": "休息一下", "mood": "caring"}),
            (
                CommandResultMessage,
                {
                    "type": "command_result",
                    "action": "light_on",
                    "success": True,
                    "message": "done",
                },
            ),
            (
                MemorySyncMessage,
                {"type": "memory_sync", "data": {"nickname": "test"}},
            ),
            (
                SensorAlertMessage,
                {
                    "type": "sensor_alert",
                    "alert": "air_quality_bad",
                    "suggestion": "开窗",
                },
            ),
        ],
    )
    def test_roundtrip(self, cls, data):
        msg = parse_server_message(data)
        assert isinstance(msg, cls)
        dumped = msg.model_dump()
        assert dumped["type"] == data["type"]

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown server"):
            parse_server_message({"type": "nonexistent"})


class TestEventSubtypes:
    """event 消息子类型验证。"""

    def test_personality_switch(self):
        msg = parse_esp32_message(
            {"type": "event", "event": "personality_switch", "value": "cool"}
        )
        assert msg.event == "personality_switch"
        assert msg.value == "cool"

    def test_treehouse_mode(self):
        msg = parse_esp32_message(
            {"type": "event", "event": "treehouse_mode", "value": True}
        )
        assert msg.event == "treehouse_mode"
        assert msg.value is True

    def test_shake_no_value(self):
        msg = parse_esp32_message({"type": "event", "event": "shake"})
        assert msg.event == "shake"
        assert msg.value is None

    def test_touch(self):
        msg = parse_esp32_message({"type": "event", "event": "touch"})
        assert msg.event == "touch"

    def test_invalid_event_type(self):
        with pytest.raises(Exception):
            parse_esp32_message({"type": "event", "event": "invalid_event"})
