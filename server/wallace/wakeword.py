"""唤醒词二次确认 — openWakeWord PC 端验证。"""

from __future__ import annotations

import asyncio
import base64
import logging

import numpy as np

logger = logging.getLogger(__name__)


class WakewordVerifier:
    """封装 openWakeWord 模型做二次确认。"""

    def __init__(self, timeout: float = 2.0, threshold: float = 0.5) -> None:
        self.timeout = timeout
        self.threshold = threshold
        self._model = None  # lazy load

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            import openwakeword  # noqa: F401

            # TODO: load custom Chinese wakeword model
            # self._model = openwakeword.Model(...)
            logger.info("openWakeWord model loaded (placeholder)")
            self._model = "placeholder"
        except ImportError:
            logger.warning("openwakeword not installed, verification disabled")
            self._model = "disabled"

    async def verify(self, audio_base64: str) -> bool:
        """二次确认唤醒词。超时则默认通过。"""
        try:
            result = await asyncio.wait_for(
                self._verify_impl(audio_base64),
                timeout=self.timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.warning("Wakeword verification timed out, defaulting to confirmed")
            return True

    async def _verify_impl(self, audio_base64: str) -> bool:
        """实际验证逻辑。"""
        self._ensure_model()
        if self._model == "disabled":
            return True

        audio_bytes = base64.b64decode(audio_base64)
        _audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # TODO: actual openWakeWord inference
        # score = self._model.predict(audio_array)
        # return score >= self.threshold
        return True
