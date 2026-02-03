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
            await engine.transcribe(audio)
            mock_thread.assert_called_once()

    async def test_transcribe_not_loaded_raises(self, asr_config):
        engine = ASREngine(asr_config)
        # _model is None
        with pytest.raises(RuntimeError, match="not loaded"):
            await engine.transcribe(np.random.randn(16000).astype(np.float32))

    def test_vad_empty_audio_no_speech(self, asr_config):
        """空音频应返回无语音。"""
        engine = ASREngine(asr_config)
        assert not engine.vad_has_speech(np.array([], dtype=np.float32))

    def test_vad_silence_no_speech(self, asr_config):
        """全零静音应检测为无语音。"""
        engine = ASREngine(asr_config)
        # 1 秒静音（全零）
        silence = np.zeros(16000, dtype=np.float32)
        assert not engine.vad_has_speech(silence)

    def test_vad_speech_detected(self, asr_config):
        """高能量信号应检测为有语音。"""
        engine = ASREngine(asr_config)
        # 默认阈值为 0.5，需要 RMS > 0.5
        # 使用大振幅正弦波（振幅 0.8，RMS ≈ 0.57 > 0.5）
        t = np.linspace(0, 1, 16000, dtype=np.float32)
        speech = 0.8 * np.sin(2 * np.pi * 1000 * t)
        assert engine.vad_has_speech(speech)

    def test_vad_low_energy_no_speech(self, asr_config):
        """低能量信号应检测为无语音。"""
        engine = ASREngine(asr_config)
        # 低振幅随机噪声（RMS << 0.5）
        low_noise = np.random.randn(16000).astype(np.float32) * 0.1
        assert not engine.vad_has_speech(low_noise)

    def test_vad_threshold_boundary(self, asr_config):
        """刚好超过阈值应检测为有语音。"""
        engine = ASREngine(asr_config)
        # 默认阈值为 0.5
        # 生成 RMS 略高于阈值的常数信号
        # RMS = sqrt(mean(x^2)) = |x| for constant signal
        # 需要 RMS > 0.5，使用常数 0.6
        signal = np.full(16000, 0.6, dtype=np.float32)
        assert engine.vad_has_speech(signal)

    def test_vad_below_threshold_no_speech(self, asr_config):
        """刚好低于阈值应检测为无语音。"""
        engine = ASREngine(asr_config)
        # 默认阈值为 0.5
        # RMS < 0.5 应无语音
        signal = np.full(16000, 0.4, dtype=np.float32)
        assert not engine.vad_has_speech(signal)

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
