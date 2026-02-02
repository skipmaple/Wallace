"""测试 asr.py — 语音识别、PCM 转换、线程调用。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from wallace.config import ASRConfig
from wallace.pipeline.asr import ASREngine


@pytest.fixture
def asr_config() -> ASRConfig:
    return ASRConfig(model="tiny", device="cpu", compute_type="float32")


class TestPCMConversion:
    """PCM int16 → numpy float32 归一化。"""

    def test_int16_to_float32(self, session):
        session.append_audio(np.array([32767, -32768, 0], dtype=np.int16).tobytes())
        arr = session.get_audio_array()
        assert arr.dtype == np.float32
        assert abs(arr[0] - 1.0) < 0.001
        assert abs(arr[1] - (-1.0)) < 0.001
        assert arr[2] == 0.0

    def test_empty_buffer(self, session):
        arr = session.get_audio_array()
        assert arr.size == 0


class TestASREngine:
    """ASR 引擎接口。"""

    async def test_transcribe_empty_audio(self, asr_config):
        engine = ASREngine(asr_config)
        engine._model = MagicMock()
        result = await engine.transcribe(np.array([], dtype=np.float32))
        assert result == ""

    async def test_transcribe_calls_to_thread(self, asr_config):
        engine = ASREngine(asr_config)

        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "你好"
        mock_model.transcribe.return_value = ([mock_segment], None)
        engine._model = mock_model

        audio = np.random.randn(16000).astype(np.float32)

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = "你好"
            result = await engine.transcribe(audio)
            mock_thread.assert_called_once()

    async def test_transcribe_not_loaded_raises(self, asr_config):
        engine = ASREngine(asr_config)
        # _model is None
        with pytest.raises(RuntimeError, match="not loaded"):
            await engine.transcribe(np.random.randn(16000).astype(np.float32))

    def test_vad_empty_audio_no_speech(self, asr_config):
        engine = ASREngine(asr_config)
        assert engine.vad_has_speech(np.array([], dtype=np.float32)) is False

    def test_vad_with_audio(self, asr_config):
        """当前 placeholder 总返回 True。"""
        engine = ASREngine(asr_config)
        audio = np.random.randn(16000).astype(np.float32)
        assert engine.vad_has_speech(audio) is True

    async def test_short_audio(self, asr_config):
        """极短音频 (<0.5s) 不应抛异常。"""
        engine = ASREngine(asr_config)
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], None)
        engine._model = mock_model

        # 0.1s audio
        audio = np.random.randn(1600).astype(np.float32)
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=""):
            result = await engine.transcribe(audio)
            assert result == ""
