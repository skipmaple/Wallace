"""语音识别 — Faster-Whisper + Silero VAD。"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from wallace.config import ASRConfig

logger = logging.getLogger(__name__)


class ASREngine:
    """封装 Faster-Whisper 模型。"""

    def __init__(self, config: ASRConfig) -> None:
        self.config = config
        self._model = None

    async def load_model(self) -> None:
        """在线程中加载模型（阻塞操作）。"""
        self._model = await asyncio.to_thread(self._load_sync)
        logger.info("ASR model loaded: %s on %s", self.config.model, self.config.device)

    def _load_sync(self):
        from faster_whisper import WhisperModel

        return WhisperModel(
            self.config.model,
            device=self.config.device,
            compute_type=self.config.compute_type,
        )

    async def transcribe(self, audio: np.ndarray) -> str:
        """转录 PCM float32 数组为文本。在线程中执行避免阻塞事件循环。"""
        if audio.size == 0:
            return ""
        if self._model is None:
            raise RuntimeError("ASR model not loaded")
        return await asyncio.to_thread(self._transcribe_sync, audio)

    def _transcribe_sync(self, audio: np.ndarray) -> str:
        segments, _ = self._model.transcribe(audio, language=self.config.language)
        return "".join(seg.text for seg in segments).strip()

    def vad_has_speech(self, audio: np.ndarray) -> bool:
        """检测音频是否包含语音。

        使用简单的能量检测：RMS 能量高于阈值视为有语音。
        对于 float32 归一化音频（范围 -1 到 1），默认阈值 0.5。
        """
        if audio.size == 0:
            return False

        # 计算 RMS 能量
        rms = np.sqrt(np.mean(audio ** 2))

        # 能量阈值（可配置，默认 0.5 适合 float32 归一化音频）
        threshold = getattr(self.config, "vad_threshold", 0.5)

        return rms > threshold
