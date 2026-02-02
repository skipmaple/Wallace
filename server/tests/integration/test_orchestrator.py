"""集成测试 orchestrator.py — 流水线串联、打断、状态机。"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from wallace.config import SensorConfig
from wallace.pipeline.orchestrator import Orchestrator
from wallace.sensor import SensorProcessor
from wallace.ws.session import PipelineState


@pytest.fixture
def sensor():
    return SensorProcessor(SensorConfig())


@pytest.fixture
def orchestrator(mock_asr, mock_llm, mock_tts, sensor):
    return Orchestrator(mock_asr, mock_llm, mock_tts, sensor)


class TestFullPipeline:
    """完整流水线。"""

    async def test_asr_to_tts_sequence(self, orchestrator, session, mock_ws):
        """完整链路：PCM → ASR → LLM → TTS → WebSocket 输出。"""
        # 模拟录音
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)

        sent = mock_ws.get_sent_json_messages()
        types = [m["type"] for m in sent]

        # 应该有 tts_start, text, tts_end
        assert "tts_start" in types
        assert "text" in types
        assert "tts_end" in types

        # 应该有二进制音频帧
        assert len(mock_ws.sent_bytes) > 0

    async def test_send_order(self, orchestrator, session, mock_ws):
        """验证消息发送顺序。"""
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)

        sent = mock_ws.get_sent_json_messages()
        types = [m["type"] for m in sent]

        # tts_start 应该在 tts_end 之前
        if "tts_start" in types and "tts_end" in types:
            assert types.index("tts_start") < types.index("tts_end")

        # text 应该在 tts_end 之前或同时
        if "text" in types and "tts_end" in types:
            assert types.index("text") <= types.index("tts_end")

    async def test_mood_in_text_message(self, orchestrator, session, mock_ws):
        """最终 text 消息应携带 mood。"""
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)

        text_msgs = mock_ws.get_sent_messages_by_type("text")
        assert len(text_msgs) > 0
        assert text_msgs[-1].get("mood") is not None


class TestSentenceSplitting:
    """流式分句。"""

    async def test_two_sentences(self, orchestrator, session, mock_ws):
        """LLM 输出含两句话 → TTS 被调用多次。"""

        async def multi_sentence_stream(messages):
            for token in ["你好。", "世界！", "[mood:happy]"]:
                yield token

        orchestrator.llm.chat_stream = multi_sentence_stream
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)

        # 应有多帧音频（至少两句 × 2帧/句）
        assert len(mock_ws.sent_bytes) >= 2

    async def test_no_punctuation(self, orchestrator, session, mock_ws):
        """无标点文本 → 流结束后整体作为一句。"""

        async def no_punct_stream(messages):
            for token in ["你好世界", "[mood:neutral]"]:
                yield token

        orchestrator.llm.chat_stream = no_punct_stream
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)
        assert len(mock_ws.sent_bytes) > 0


class TestInterruption:
    """打断处理。"""

    async def test_cancel_during_processing(self, orchestrator, session, mock_ws):
        """PROCESSING 状态下打断。"""
        # 模拟一个长时间运行的流水线
        slow_called = asyncio.Event()

        async def slow_stream(messages):
            slow_called.set()
            await asyncio.sleep(10)
            yield "never"

        orchestrator.llm.chat_stream = slow_stream

        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        await orchestrator.handle_audio_start(session)

        # 等待录音完成
        session.transition_to(PipelineState.PROCESSING)
        task = asyncio.create_task(orchestrator._run_pipeline(session))
        session.pipeline_task = task

        await slow_called.wait()

        # 打断
        await orchestrator.cancel_pipeline(session)
        assert session.state == PipelineState.IDLE
        assert session.pipeline_task is None

    async def test_cancel_recovers_to_idle(self, orchestrator, session):
        """打断后状态回到 IDLE。"""
        await orchestrator.cancel_pipeline(session)
        assert session.state == PipelineState.IDLE


class TestTreehouseMode:
    """树洞模式。"""

    async def test_treehouse_asr_only(self, orchestrator, session, mock_ws):
        session.treehouse_mode = True
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)

        # 不应有 TTS 输出
        assert len(mock_ws.sent_bytes) == 0
        sent = mock_ws.get_sent_json_messages()
        types = [m["type"] for m in sent]
        assert "tts_start" not in types
        assert session.state == PipelineState.IDLE


class TestEmptyResults:
    """空结果处理。"""

    async def test_asr_empty(self, orchestrator, session, mock_ws):
        orchestrator.asr.transcribe = AsyncMock(return_value="")
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)
        assert session.state == PipelineState.IDLE
        assert len(mock_ws.sent_bytes) == 0

    async def test_vad_no_speech(self, orchestrator, session, mock_ws):
        orchestrator.asr.vad_has_speech = MagicMock(return_value=False)
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)
        assert session.state == PipelineState.IDLE

    async def test_llm_empty(self, orchestrator, session, mock_ws):
        async def empty_stream(messages):
            return
            yield  # make it async generator

        orchestrator.llm.chat_stream = empty_stream
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)
        assert len(mock_ws.sent_bytes) == 0


class TestStateMachine:
    """状态机转换完整性。"""

    async def test_normal_flow_states(self, orchestrator, session):
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        states = [session.state]

        await orchestrator.handle_audio_start(session)
        states.append(session.state)

        session.transition_to(PipelineState.PROCESSING)
        states.append(session.state)

        await orchestrator._run_pipeline(session)
        states.append(session.state)

        assert PipelineState.RECORDING in states
        assert PipelineState.PROCESSING in states
        assert states[-1] == PipelineState.IDLE
