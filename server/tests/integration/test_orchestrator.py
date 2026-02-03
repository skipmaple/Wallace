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

    @pytest.mark.parametrize("punct,label", [
        ("。", "句号"),
        ("！", "感叹号"),
        ("？", "问号"),
        ("；", "分号"),
        ("\n", "换行"),
    ])
    async def test_punctuation_triggers_split(
        self, orchestrator, session, mock_ws, punct, label
    ):
        """各标点符号都应触发分句：{label}"""
        tts_call_count = [0]

        async def track_tts(text):
            tts_call_count[0] += 1
            yield b"\x00" * 1024

        orchestrator.tts.synthesize = track_tts

        async def punct_stream(messages):
            yield f"第一句{punct}第二句[mood:happy]"

        orchestrator.llm.chat_stream = punct_stream
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)

        # 应有两次 TTS 调用（两个句子）
        assert tts_call_count[0] >= 2, \
            f"Punctuation '{repr(punct)}' should trigger sentence split, got {tts_call_count[0]} TTS calls"

    async def test_multiple_punctuation_multiple_sentences(
        self, orchestrator, session, mock_ws
    ):
        """多个标点应产生多个句子（流式逐句输出）。"""
        tts_texts = []

        async def track_tts(text):
            tts_texts.append(text)
            yield b"\x00" * 1024

        orchestrator.tts.synthesize = track_tts

        async def multi_punct_stream(messages):
            # 模拟真实 LLM 逐句输出
            yield "第一句。"
            yield "第二句！"
            yield "第三句？"
            yield "[mood:happy]"

        orchestrator.llm.chat_stream = multi_punct_stream
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)

        # 应有三次 TTS 调用
        assert len(tts_texts) >= 3, \
            f"Expected at least 3 TTS calls, got {len(tts_texts)}: {tts_texts}"

    async def test_token_by_token_splitting(self, orchestrator, session, mock_ws):
        """逐 token 流式输出也应正确分句。"""
        tts_texts = []

        async def track_tts(text):
            tts_texts.append(text)
            yield b"\x00" * 1024

        orchestrator.tts.synthesize = track_tts

        async def token_by_token_stream(messages):
            # 模拟真实 LLM 逐字输出
            for char in "你好。世界！[mood:happy]":
                yield char

        orchestrator.llm.chat_stream = token_by_token_stream
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)

        # 应有两次 TTS 调用（"你好。" 和 "世界！"）
        assert len(tts_texts) >= 2, \
            f"Token-by-token should trigger splits, got {len(tts_texts)}: {tts_texts}"


class TestInterruption:
    """打断处理。"""

    async def test_cancel_during_processing(self, orchestrator, session, mock_ws):
        """PROCESSING 状态下打断：取消任务，状态回 IDLE，不发送 tts_cancel。

        注意：流水线在 LLM 流开始前就转换到 SPEAKING 状态，
        所以要测试 PROCESSING 状态取消，需要在 ASR 阶段模拟慢操作。
        """
        slow_called = asyncio.Event()

        # 模拟慢 ASR（在 PROCESSING 状态期间）
        async def slow_transcribe(_audio):
            slow_called.set()
            await asyncio.sleep(10)  # 长时间阻塞在 PROCESSING 状态
            return "测试文本"

        orchestrator.asr.transcribe = slow_transcribe

        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        task = asyncio.create_task(orchestrator._run_pipeline(session))
        session.pipeline_task = task

        await slow_called.wait()
        # 此时还在 ASR 阶段，状态仍为 PROCESSING
        assert session.state == PipelineState.PROCESSING, "ASR 期间应保持 PROCESSING 状态"

        # 打断
        await orchestrator.cancel_pipeline(session)
        assert session.state == PipelineState.IDLE
        assert session.pipeline_task is None

        # PROCESSING 状态打断不发 tts_cancel（因为还没开始说话）
        sent = mock_ws.get_sent_json_messages()
        cancel_msgs = [m for m in sent if m.get("type") == "tts_cancel"]
        assert len(cancel_msgs) == 0, "PROCESSING 状态打断不应发送 tts_cancel"

    async def test_cancel_during_speaking_sends_tts_cancel(self, orchestrator, session, mock_ws):
        """SPEAKING 状态下打断：必须发送 tts_cancel 通知 ESP32 停止播放。"""
        slow_called = asyncio.Event()

        async def slow_tts(text):
            slow_called.set()
            for _ in range(100):
                await asyncio.sleep(0.1)
                yield b"\x00" * 1024

        orchestrator.tts.synthesize = slow_tts

        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        task = asyncio.create_task(orchestrator._run_pipeline(session))
        session.pipeline_task = task

        # 等待 TTS 开始（进入 SPEAKING 状态）
        await slow_called.wait()
        await asyncio.sleep(0.05)  # 确保状态已切换
        assert session.state == PipelineState.SPEAKING

        # 打断
        await orchestrator.cancel_pipeline(session)

        assert session.state == PipelineState.IDLE

        # SPEAKING 状态打断必须发送 tts_cancel
        sent = mock_ws.get_sent_json_messages()
        cancel_msgs = [m for m in sent if m.get("type") == "tts_cancel"]
        assert len(cancel_msgs) > 0, "SPEAKING 状态打断必须发送 tts_cancel"

    async def test_cancel_recovers_to_idle(self, orchestrator, session):
        """打断后状态回到 IDLE。"""
        await orchestrator.cancel_pipeline(session)
        assert session.state == PipelineState.IDLE

    async def test_interrupt_then_new_pipeline_works(self, orchestrator, session, mock_ws):
        """打断后应能启动新的流水线。"""
        slow_called = asyncio.Event()

        async def slow_stream(messages):
            slow_called.set()
            await asyncio.sleep(10)
            yield "never"

        orchestrator.llm.chat_stream = slow_stream

        # 第一个流水线
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)
        task = asyncio.create_task(orchestrator._run_pipeline(session))
        session.pipeline_task = task

        await slow_called.wait()

        # 打断
        await orchestrator.cancel_pipeline(session)
        assert session.state == PipelineState.IDLE

        mock_ws.sent_text.clear()
        mock_ws.sent_bytes.clear()

        # 第二个流水线应能正常完成
        async def fast_stream(messages):
            yield "你好！[mood:happy]"

        orchestrator.llm.chat_stream = fast_stream
        session.append_audio(np.zeros(16000, dtype=np.int16).tobytes())
        session.state = PipelineState.RECORDING
        session.transition_to(PipelineState.PROCESSING)

        await orchestrator._run_pipeline(session)

        assert session.state == PipelineState.IDLE
        sent = mock_ws.get_sent_json_messages()
        types = [m["type"] for m in sent]
        assert "tts_start" in types, "新流水线应有 tts_start"
        assert "tts_end" in types, "新流水线应有 tts_end"


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


class TestRandomFact:
    """摇一摇冷知识功能。"""

    async def test_push_random_fact_success(self, orchestrator, session, mock_ws):
        """摇一摇 → LLM 生成 → TTS 推送。"""

        async def fact_stream(messages):
            for token in ["蜂蜜永远不会变质！", "[mood:surprised]"]:
                yield token

        orchestrator.llm.chat_stream = fact_stream
        assert session.state == PipelineState.IDLE

        await orchestrator.push_random_fact(session)

        # 应回到 IDLE
        assert session.state == PipelineState.IDLE

        # 应发送 TTS 消息
        sent = mock_ws.get_sent_json_messages()
        types = [m["type"] for m in sent]
        assert "tts_start" in types
        assert "text" in types
        assert "tts_end" in types

        # 应发送音频帧
        assert len(mock_ws.sent_bytes) > 0

        # text 消息应包含 mood
        text_msgs = [m for m in sent if m["type"] == "text"]
        assert len(text_msgs) > 0
        assert text_msgs[-1].get("mood") == "surprised"

    async def test_push_random_fact_busy_ignored(self, orchestrator, session, mock_ws):
        """忙碌状态时忽略 shake。"""
        session.state = PipelineState.SPEAKING

        await orchestrator.push_random_fact(session)

        # 状态应保持不变
        assert session.state == PipelineState.SPEAKING

        # 不应发送任何消息
        assert len(mock_ws.get_sent_json_messages()) == 0
        assert len(mock_ws.sent_bytes) == 0

    async def test_push_random_fact_no_punct(self, orchestrator, session, mock_ws):
        """无标点冷知识也应正常处理。"""

        async def fact_stream_no_punct(messages):
            # 无标点，应在流结束后整体作为一句
            yield "蜂蜜永远不会变质[mood:surprised]"

        orchestrator.llm.chat_stream = fact_stream_no_punct

        await orchestrator.push_random_fact(session)

        # 应回到 IDLE
        assert session.state == PipelineState.IDLE

        # 应发送 TTS 消息
        sent = mock_ws.get_sent_json_messages()
        types = [m["type"] for m in sent]
        assert "tts_start" in types
        assert "tts_end" in types
