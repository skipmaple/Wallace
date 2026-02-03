"""会话对象 — 聚合单个 WebSocket 连接的所有状态。"""

from __future__ import annotations

import asyncio
import enum
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from fastapi import WebSocket


class PipelineState(enum.Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@dataclass
class SensorData:
    temp: float = 0.0
    humidity: float = 0.0
    light: float = 0.0
    air_quality: float = 0.0
    updated_at: float = 0.0


@dataclass
class UserMemory:
    nickname: str = ""
    preferences: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    recent_topics: list[str] = field(default_factory=list)
    important_dates: dict[str, str] = field(default_factory=dict)
    interaction_count: int = 0
    first_met: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "nickname": self.nickname,
            "preferences": self.preferences,
            "interests": self.interests,
            "recent_topics": self.recent_topics,
            "important_dates": self.important_dates,
            "interaction_count": self.interaction_count,
            "first_met": self.first_met,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserMemory:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class Session:
    """每个 WebSocket 连接一个 Session 实例。"""

    def __init__(self, user_id: str, ws: WebSocket) -> None:
        self.user_id = user_id
        self.ws = ws

        # 状态
        self.personality: str = "normal"
        self.treehouse_mode: bool = False
        self.tts_backend: str = "edge"
        self.state: PipelineState = PipelineState.IDLE

        # 流水线
        self.pipeline_task: asyncio.Task | None = None
        self.random_fact_task: asyncio.Task | None = None
        self.pipeline_lock = asyncio.Lock()
        self.audio_buffer = bytearray()
        self.wakeword_confirmed = asyncio.Event()

        # 缓存
        self.sensor_cache = SensorData()
        self.proximity_present: bool = True
        self.last_heartbeat: float = time.monotonic()

        # 对话
        self.chat_history: list[dict[str, str]] = []
        self.memory = UserMemory()

    def transition_to(self, new_state: PipelineState) -> None:
        """状态机转换，校验合法路径。"""
        valid = {
            PipelineState.IDLE: {PipelineState.RECORDING},
            PipelineState.RECORDING: {PipelineState.PROCESSING, PipelineState.IDLE},
            PipelineState.PROCESSING: {PipelineState.SPEAKING, PipelineState.IDLE},
            PipelineState.SPEAKING: {PipelineState.IDLE, PipelineState.RECORDING},
        }
        allowed = valid.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid state transition: {self.state.value} → {new_state.value}"
            )
        self.state = new_state

    def append_audio(self, data: bytes) -> None:
        """追加音频二进制帧到缓冲。"""
        self.audio_buffer.extend(data)

    def get_audio_array(self) -> np.ndarray:
        """将缓冲转为 numpy float32 归一化数组。"""
        if not self.audio_buffer:
            return np.array([], dtype=np.float32)
        arr = np.frombuffer(bytes(self.audio_buffer), dtype=np.int16)
        return arr.astype(np.float32) / 32768.0

    def clear_audio(self) -> None:
        self.audio_buffer.clear()

    def update_heartbeat(self) -> None:
        self.last_heartbeat = time.monotonic()
