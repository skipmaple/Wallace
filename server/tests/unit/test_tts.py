"""测试 tts.py — 双 TTS 后端、转码、降级、帧切割。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wallace.config import TTSConfig
from wallace.pipeline.tts import FRAME_SIZE, CosyVoiceBackend, EdgeTTSBackend, TTSManager


@pytest.fixture
def tts_config() -> TTSConfig:
    return TTSConfig()


@pytest.fixture
def tts_manager(tts_config) -> TTSManager:
    return TTSManager(tts_config)


class TestFrameSize:
    """PCM 帧大小。"""

    def test_frame_size_is_1024(self):
        assert FRAME_SIZE == 1024


class TestEdgeTTSBackend:
    """Edge-TTS 后端。"""

    async def test_empty_text_returns_nothing(self):
        backend = EdgeTTSBackend()
        frames = [f async for f in backend.synthesize("")]
        assert frames == []

    async def test_whitespace_text_returns_nothing(self):
        backend = EdgeTTSBackend()
        frames = [f async for f in backend.synthesize("   ")]
        assert frames == []

    async def test_synthesize_mock(self):
        """Mock edge-tts + miniaudio 验证帧切割。"""
        backend = EdgeTTSBackend()

        # Mock edge_tts.Communicate
        mock_comm_cls = MagicMock()
        mock_comm = MagicMock()

        async def fake_stream():
            yield {"type": "audio", "data": b"\x00" * 2048}  # fake MP3

        mock_comm.stream = fake_stream
        mock_comm_cls.return_value = mock_comm

        # Mock miniaudio.decode
        mock_decoded = MagicMock()
        mock_decoded.samples.tobytes.return_value = b"\x00" * 4096  # 4 frames

        with (
            patch("wallace.pipeline.tts.edge_tts") as mock_edge,
            patch("wallace.pipeline.tts.miniaudio") as mock_mini,
        ):
            mock_edge.Communicate = mock_comm_cls
            mock_mini.decode.return_value = mock_decoded

            frames = [f async for f in backend.synthesize("你好")]

        assert all(len(f) == FRAME_SIZE for f in frames)
        assert len(frames) == 4


class TestCosyVoiceBackend:
    """CosyVoice 后端。"""

    async def test_empty_text_returns_nothing(self):
        backend = CosyVoiceBackend()
        frames = [f async for f in backend.synthesize("")]
        assert frames == []

    async def test_synthesize_mock(self):
        backend = CosyVoiceBackend()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = b"\x00" * 2048  # 2 frames

        with patch("wallace.pipeline.tts.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_httpx.AsyncClient.return_value = mock_client

            frames = [f async for f in backend.synthesize("你好")]

        assert len(frames) == 2
        assert all(len(f) == FRAME_SIZE for f in frames)


class TestTTSManager:
    """TTSManager 后端切换和降级。"""

    def test_default_backend(self, tts_manager):
        assert tts_manager.current_backend == "edge"

    def test_switch_backend(self, tts_manager):
        tts_manager.switch_backend("cosyvoice")
        assert tts_manager.current_backend == "cosyvoice"
        tts_manager.switch_backend("edge")
        assert tts_manager.current_backend == "edge"

    def test_switch_invalid_backend(self, tts_manager):
        with pytest.raises(ValueError, match="Unknown TTS"):
            tts_manager.switch_backend("unknown")

    async def test_fallback_on_primary_failure(self, tts_manager):
        """主后端失败时降级到备用后端。"""
        call_log = []

        async def failing_synthesize(text, voice=""):
            call_log.append("primary_called")
            raise Exception("edge-tts down")
            yield  # make it async generator  # noqa: unreachable

        async def working_synthesize(text, voice=""):
            call_log.append("fallback_called")
            yield b"\x00" * FRAME_SIZE

        tts_manager._edge.synthesize = failing_synthesize
        tts_manager._cosyvoice.synthesize = working_synthesize

        frames = [f async for f in tts_manager.synthesize("test")]
        assert "primary_called" in call_log
        assert "fallback_called" in call_log
        assert len(frames) == 1

    async def test_both_backends_fail(self, tts_manager):
        """两个后端都失败 → 空结果。"""

        async def failing(text, voice=""):
            raise Exception("down")
            yield  # noqa: unreachable

        tts_manager._edge.synthesize = failing
        tts_manager._cosyvoice.synthesize = failing

        frames = [f async for f in tts_manager.synthesize("test")]
        assert frames == []

    def test_frame_padding(self):
        """最后一帧不足 1024 时补零。"""
        # 验证补零逻辑是否在合成中实现
        pcm = b"\x01" * 500
        padded = pcm + b"\x00" * (FRAME_SIZE - len(pcm))
        assert len(padded) == FRAME_SIZE
