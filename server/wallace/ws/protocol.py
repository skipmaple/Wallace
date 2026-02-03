"""WebSocket 消息类型定义 — Pydantic 模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


# ────────────────────── 基础 ──────────────────────

class BaseMessage(BaseModel):
    type: str


# ────────────────────── ESP32 → Server ──────────────────────

class PingMessage(BaseMessage):
    type: Literal["ping"] = "ping"


class AudioStartMessage(BaseMessage):
    type: Literal["audio_start"] = "audio_start"


class AudioEndMessage(BaseMessage):
    type: Literal["audio_end"] = "audio_end"


class WakewordVerifyMessage(BaseMessage):
    type: Literal["wakeword_verify"] = "wakeword_verify"
    audio: str  # base64 encoded PCM


class SensorMessage(BaseMessage):
    type: Literal["sensor"] = "sensor"
    temp: float
    humidity: float
    light: float
    air_quality: float


class ProximityMessage(BaseMessage):
    type: Literal["proximity"] = "proximity"
    distance: float
    user_present: bool


class DeviceStateMessage(BaseMessage):
    type: Literal["device_state"] = "device_state"
    battery_pct: int
    power_mode: str
    wifi_rssi: int


class EventMessage(BaseMessage):
    type: Literal["event"] = "event"
    event: Literal["personality_switch", "treehouse_mode", "shake", "touch"]
    value: Any = None


class LocalCmdMessage(BaseMessage):
    type: Literal["local_cmd"] = "local_cmd"
    action: str


class ImageMessage(BaseMessage):
    type: Literal["image"] = "image"
    data: str  # base64


class ConfigMessage(BaseMessage):
    type: Literal["config"] = "config"
    tts_backend: Literal["edge", "cosyvoice"]


# ────────────────────── Server → ESP32 ──────────────────────

class WakewordResultMessage(BaseMessage):
    type: Literal["wakeword_result"] = "wakeword_result"
    confirmed: bool


class TTSStartMessage(BaseMessage):
    type: Literal["tts_start"] = "tts_start"
    mood: str = "thinking"


class TTSCancelMessage(BaseMessage):
    type: Literal["tts_cancel"] = "tts_cancel"


class TTSEndMessage(BaseMessage):
    type: Literal["tts_end"] = "tts_end"


class PongMessage(BaseMessage):
    type: Literal["pong"] = "pong"


class SessionRestoreMessage(BaseMessage):
    type: Literal["session_restore"] = "session_restore"
    personality: str
    treehouse: bool
    tts_backend: str


class TextMessage(BaseMessage):
    type: Literal["text"] = "text"
    content: str
    partial: bool = False
    mood: str | None = None


class CareMessage(BaseMessage):
    type: Literal["care"] = "care"
    content: str
    mood: str


class CommandResultMessage(BaseMessage):
    type: Literal["command_result"] = "command_result"
    action: str
    success: bool
    message: str = ""


class MemorySyncMessage(BaseMessage):
    type: Literal["memory_sync"] = "memory_sync"
    data: dict[str, Any]


class SensorAlertMessage(BaseMessage):
    type: Literal["sensor_alert"] = "sensor_alert"
    alert: str
    suggestion: str


# ────────────────────── 解析 ──────────────────────

_ESP32_TYPES: dict[str, type[BaseMessage]] = {
    "ping": PingMessage,
    "audio_start": AudioStartMessage,
    "audio_end": AudioEndMessage,
    "wakeword_verify": WakewordVerifyMessage,
    "sensor": SensorMessage,
    "proximity": ProximityMessage,
    "device_state": DeviceStateMessage,
    "event": EventMessage,
    "local_cmd": LocalCmdMessage,
    "image": ImageMessage,
    "config": ConfigMessage,
}

_SERVER_TYPES: dict[str, type[BaseMessage]] = {
    "wakeword_result": WakewordResultMessage,
    "tts_start": TTSStartMessage,
    "tts_cancel": TTSCancelMessage,
    "tts_end": TTSEndMessage,
    "pong": PongMessage,
    "session_restore": SessionRestoreMessage,
    "text": TextMessage,
    "care": CareMessage,
    "command_result": CommandResultMessage,
    "memory_sync": MemorySyncMessage,
    "sensor_alert": SensorAlertMessage,
}


def parse_esp32_message(data: dict) -> BaseMessage:
    """解析 ESP32 → Server 的 JSON 消息。"""
    msg_type = data.get("type")
    cls = _ESP32_TYPES.get(msg_type)  # type: ignore[arg-type]
    if cls is None:
        raise ValueError(f"Unknown ESP32 message type: {msg_type!r}")
    return cls(**data)


def parse_server_message(data: dict) -> BaseMessage:
    """解析 Server → ESP32 的 JSON 消息。"""
    msg_type = data.get("type")
    cls = _SERVER_TYPES.get(msg_type)  # type: ignore[arg-type]
    if cls is None:
        raise ValueError(f"Unknown server message type: {msg_type!r}")
    return cls(**data)
