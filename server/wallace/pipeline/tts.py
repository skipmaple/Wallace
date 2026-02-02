"""语音合成 — 双 TTS 后端 (Edge-TTS + CosyVoice)。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import edge_tts
import httpx
import miniaudio

if TYPE_CHECKING:
    from wallace.config import TTSConfig

logger = logging.getLogger(__name__)

# PCM 帧大小：512 samples × 2 bytes = 1024 bytes
FRAME_SIZE = 1024


class TTSBackend(ABC):
    """TTS 后端协议。"""

    @abstractmethod
    async def synthesize(self, text: str, voice: str = "") -> AsyncIterator[bytes]:
        """合成文本为 PCM 16kHz 16bit mono 帧。"""
        ...  # pragma: no cover


class EdgeTTSBackend(TTSBackend):
    """Edge-TTS 后端 — 云端合成，MP3 转 PCM。"""

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural") -> None:
        self.default_voice = voice

    async def synthesize(self, text: str, voice: str = "") -> AsyncIterator[bytes]:
        if not text.strip():
            return

        voice = voice or self.default_voice
        communicate = edge_tts.Communicate(text, voice)

        # 收集整句 MP3 数据
        mp3_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_chunks.append(chunk["data"])

        if not mp3_chunks:
            return

        mp3_data = b"".join(mp3_chunks)
        decoded = miniaudio.decode(mp3_data, sample_rate=16000, nchannels=1)
        pcm_bytes = decoded.samples.tobytes()

        # 按 FRAME_SIZE 切割
        for i in range(0, len(pcm_bytes), FRAME_SIZE):
            frame = pcm_bytes[i : i + FRAME_SIZE]
            if len(frame) < FRAME_SIZE:
                frame = frame + b"\x00" * (FRAME_SIZE - len(frame))
            yield frame


class CosyVoiceBackend(TTSBackend):
    """CosyVoice 2 后端 — 本地 GPU 合成，直出 PCM。"""

    def __init__(self, url: str = "http://localhost:9880", voice: str = "default") -> None:
        self.url = url
        self.default_voice = voice

    async def synthesize(self, text: str, voice: str = "") -> AsyncIterator[bytes]:
        if not text.strip():
            return

        voice = voice or self.default_voice
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.url}/tts",
                json={"text": text, "voice": voice},
            )
            resp.raise_for_status()
            pcm_bytes = resp.content

        for i in range(0, len(pcm_bytes), FRAME_SIZE):
            frame = pcm_bytes[i : i + FRAME_SIZE]
            if len(frame) < FRAME_SIZE:
                frame = frame + b"\x00" * (FRAME_SIZE - len(frame))
            yield frame


class TTSManager:
    """管理双 TTS 后端 + 降级逻辑。"""

    def __init__(self, config: TTSConfig) -> None:
        self.config = config
        self._edge = EdgeTTSBackend(config.edge_voice)
        self._cosyvoice = CosyVoiceBackend(config.cosyvoice_url, config.cosyvoice_voice)
        self._current: str = config.default_backend

    @property
    def current_backend(self) -> str:
        return self._current

    def switch_backend(self, backend: str) -> None:
        if backend not in ("edge", "cosyvoice"):
            raise ValueError(f"Unknown TTS backend: {backend}")
        self._current = backend

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """合成文本，自动降级。"""
        primary = self._edge if self._current == "edge" else self._cosyvoice
        fallback = self._cosyvoice if self._current == "edge" else self._edge

        try:
            async for frame in primary.synthesize(text):
                yield frame
            return
        except Exception as e:
            logger.warning("Primary TTS (%s) failed: %s, falling back", self._current, e)

        try:
            async for frame in fallback.synthesize(text):
                yield frame
        except Exception as e2:
            logger.error("Both TTS backends failed: %s", e2)
            # 不产出音频，调用方应处理空结果
