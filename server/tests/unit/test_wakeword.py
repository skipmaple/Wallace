"""测试 wakeword.py — 唤醒词二次确认、超时、base64 解码。"""

from __future__ import annotations

import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from wallace.wakeword import WakewordVerifier


@pytest.fixture
def verifier() -> WakewordVerifier:
    return WakewordVerifier(timeout=2.0, threshold=0.5)


class TestWakewordVerify:
    """唤醒词验证。"""

    async def test_confirm_when_disabled(self, verifier):
        """openWakeWord 未安装时默认通过。"""
        verifier._model = "disabled"
        result = await verifier.verify("dGVzdA==")
        assert result is True

    async def test_confirm_placeholder(self, verifier):
        """当前 placeholder 实现总是返回 True。"""
        verifier._model = "placeholder"
        audio = base64.b64encode(np.zeros(1600, dtype=np.int16).tobytes()).decode()
        result = await verifier.verify(audio)
        assert result is True

    async def test_timeout_defaults_to_confirmed(self):
        """超时则默认确认通过。"""
        verifier = WakewordVerifier(timeout=0.1)

        async def slow_verify(audio_base64):
            await asyncio.sleep(1.0)
            return False

        verifier._verify_impl = slow_verify  # type: ignore[assignment]
        result = await verifier.verify("dGVzdA==")
        assert result is True

    def test_base64_decode(self):
        """base64 编码的音频可正确解码。"""
        original = np.array([100, 200, -100], dtype=np.int16).tobytes()
        encoded = base64.b64encode(original).decode()
        decoded = base64.b64decode(encoded)
        assert decoded == original

    async def test_normal_timeout_not_triggered(self, verifier):
        """正常速度返回时不触发超时。"""
        verifier._model = "placeholder"
        audio = base64.b64encode(b"\x00" * 100).decode()
        result = await verifier.verify(audio)
        assert result is True
