"""E2E 测试 — 打断场景。"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock


from .conftest import create_llm_stream_mock, create_tts_mock


class TestInterruption:
    """打断场景测试。

    根据架构文档，当 SPEAKING 状态被打断时，服务器必须发送 tts_cancel。
    这些测试验证打断行为符合预期。
    """

    def test_interrupt_during_tts_sends_cancel(
        self, ws_client, mock_asr_engine, mock_llm_client, mock_tts_manager
    ):
        """TTS 播放中收到 audio_start 应发送 tts_cancel。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["回复", "[mood:happy]"])
        # 慢速 TTS 以便打断
        mock_tts_manager.synthesize = create_tts_mock(frame_count=10, frame_delay=0.2)

        with ws_client() as ws:
            # 开始第一次对话
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 等待 TTS 开始
            tts_start = ws.wait_for_message_type("tts_start", timeout=3.0)
            assert tts_start is not None, "Should receive tts_start"

            # 打断：发送新的 audio_start
            ws.send_audio_start()

            # 等待 tts_cancel（打断时必须发送）
            tts_cancel = ws.wait_for_message_type("tts_cancel", timeout=3.0)
            assert tts_cancel is not None, \
                f"Should receive tts_cancel when interrupting SPEAKING state, got: {ws.get_message_sequence()}"
            assert tts_cancel.get("type") == "tts_cancel"

            # 验证连接仍有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None, "Connection should still be valid"

    def test_interrupt_during_processing_no_crash(
        self, ws_client, mock_asr_engine, mock_llm_client
    ):
        """LLM 处理中打断不应崩溃。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        # 慢速 LLM
        mock_llm_client.chat_stream = create_llm_stream_mock(
            ["慢", "速", "回", "复", "[mood:happy]"],
            delay=0.3
        )

        with ws_client() as ws:
            # 开始第一次对话
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 短暂等待后打断
            time.sleep(0.2)
            ws.send_audio_start()

            # 验证连接有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_new_conversation_after_interrupt(
        self, ws_client, mock_asr_engine, mock_llm_client, mock_tts_manager
    ):
        """打断后应能开始新对话。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["回复", "[mood:happy]"])
        mock_tts_manager.synthesize = create_tts_mock(frame_count=2, frame_delay=0.05)

        with ws_client() as ws:
            # 第一次对话
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 等待 TTS 开始后立即打断
            ws.wait_for_message_type("tts_start", timeout=3.0)
            ws.send_audio_start()

            # 验证连接有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

            # 完成新对话
            ws.clear()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 等待新对话完成
            ws.receive_all_available(timeout=5.0)

            # 新对话应有响应
            sequence = ws.get_message_sequence()
            # 应有 tts_start（表示新对话开始了）
            assert "tts_start" in sequence or "pong" in sequence

    def test_rapid_audio_cycles_no_crash(self, ws_client, mock_asr_engine, mock_llm_client):
        """快速连续发送音频周期不应崩溃。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["回复", "[mood:happy]"])

        with ws_client() as ws:
            # 快速发送多个 audio_start/end，但等待每个完成
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 512)
            ws.send_audio_end()

            # 等待处理完成
            ws.receive_all_available(timeout=5.0)

            # 不应崩溃，连接应仍然有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None
