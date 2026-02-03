"""测试 session.py — 会话对象、状态机、audio_buffer。"""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from wallace.ws.session import PipelineState, Session, UserMemory


class TestSessionCreation:
    """Session 默认状态。"""

    def test_default_state(self, mock_ws):
        s = Session("u1", mock_ws)
        assert s.user_id == "u1"
        assert s.personality == "normal"
        assert s.treehouse_mode is False
        assert s.tts_backend == "edge"
        assert s.state == PipelineState.IDLE
        assert s.pipeline_task is None
        assert len(s.audio_buffer) == 0
        assert s.chat_history == []
        assert s.proximity_present is True


class TestStateMachine:
    """状态机转换合法性。"""

    def test_valid_full_path(self, mock_ws):
        s = Session("u1", mock_ws)
        s.transition_to(PipelineState.RECORDING)
        assert s.state == PipelineState.RECORDING
        s.transition_to(PipelineState.PROCESSING)
        assert s.state == PipelineState.PROCESSING
        s.transition_to(PipelineState.SPEAKING)
        assert s.state == PipelineState.SPEAKING
        s.transition_to(PipelineState.IDLE)
        assert s.state == PipelineState.IDLE

    def test_recording_to_idle(self, mock_ws):
        """录音中可以直接回到 IDLE（如唤醒词确认失败）。"""
        s = Session("u1", mock_ws)
        s.transition_to(PipelineState.RECORDING)
        s.transition_to(PipelineState.IDLE)
        assert s.state == PipelineState.IDLE

    def test_speaking_to_recording(self, mock_ws):
        """播放中被打断跳到 RECORDING。"""
        s = Session("u1", mock_ws)
        s.transition_to(PipelineState.RECORDING)
        s.transition_to(PipelineState.PROCESSING)
        s.transition_to(PipelineState.SPEAKING)
        s.transition_to(PipelineState.RECORDING)
        assert s.state == PipelineState.RECORDING

    def test_invalid_idle_to_speaking(self, mock_ws):
        s = Session("u1", mock_ws)
        with pytest.raises(ValueError, match="Invalid state transition"):
            s.transition_to(PipelineState.SPEAKING)

    def test_invalid_idle_to_processing(self, mock_ws):
        s = Session("u1", mock_ws)
        with pytest.raises(ValueError, match="Invalid state transition"):
            s.transition_to(PipelineState.PROCESSING)

    def test_invalid_recording_to_speaking(self, mock_ws):
        s = Session("u1", mock_ws)
        s.transition_to(PipelineState.RECORDING)
        with pytest.raises(ValueError):
            s.transition_to(PipelineState.SPEAKING)


class TestAudioBuffer:
    """录音缓冲操作。"""

    def test_append_and_clear(self, mock_ws):
        s = Session("u1", mock_ws)
        s.append_audio(b"\x01\x02\x03\x04")
        s.append_audio(b"\x05\x06")
        assert len(s.audio_buffer) == 6
        s.clear_audio()
        assert len(s.audio_buffer) == 0

    def test_get_audio_array_empty(self, mock_ws):
        s = Session("u1", mock_ws)
        arr = s.get_audio_array()
        assert arr.dtype == np.float32
        assert arr.size == 0

    def test_get_audio_array_normalized(self, mock_ws):
        s = Session("u1", mock_ws)
        # int16 max = 32767 → should normalize to ~1.0
        s.append_audio(np.array([32767, -32768, 0], dtype=np.int16).tobytes())
        arr = s.get_audio_array()
        assert arr.dtype == np.float32
        assert abs(arr[0] - 1.0) < 0.001
        assert abs(arr[1] - (-1.0)) < 0.001
        assert arr[2] == 0.0

    def test_get_audio_array_multiple_appends(self, mock_ws):
        s = Session("u1", mock_ws)
        # 2 samples each append
        s.append_audio(np.array([100, 200], dtype=np.int16).tobytes())
        s.append_audio(np.array([300, 400], dtype=np.int16).tobytes())
        arr = s.get_audio_array()
        assert len(arr) == 4


class TestPipelineLock:
    """pipeline_lock 并发控制。"""

    async def test_lock_mutual_exclusion(self, mock_ws):
        s = Session("u1", mock_ws)
        results = []

        async def worker(name: str):
            async with s.pipeline_lock:
                results.append(f"{name}_enter")
                await asyncio.sleep(0.05)
                results.append(f"{name}_exit")

        await asyncio.gather(worker("a"), worker("b"))
        # a 和 b 不会交错
        assert results[0].endswith("_enter")
        assert results[1].endswith("_exit")
        assert results[2].endswith("_enter")
        assert results[3].endswith("_exit")


class TestWakewordEvent:
    """wakeword_confirmed Event 行为。"""

    async def test_set_and_wait(self, mock_ws):
        s = Session("u1", mock_ws)
        assert not s.wakeword_confirmed.is_set()

        s.wakeword_confirmed.set()
        assert s.wakeword_confirmed.is_set()

        # wait should return immediately
        await asyncio.wait_for(s.wakeword_confirmed.wait(), timeout=0.1)

        s.wakeword_confirmed.clear()
        assert not s.wakeword_confirmed.is_set()


class TestUserMemory:
    """UserMemory 序列化。"""

    def test_to_dict_roundtrip(self):
        mem = UserMemory(nickname="test", interests=["coding"])
        d = mem.to_dict()
        mem2 = UserMemory.from_dict(d)
        assert mem2.nickname == "test"
        assert mem2.interests == ["coding"]

    def test_from_dict_ignores_extra_keys(self):
        mem = UserMemory.from_dict({"nickname": "test", "extra_field": "ignored"})
        assert mem.nickname == "test"
