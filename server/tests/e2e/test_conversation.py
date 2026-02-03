"""E2E 测试 — 对话流程。"""

from __future__ import annotations

from unittest.mock import AsyncMock

from .conftest import (
    assert_has_binary_frames,
    create_llm_stream_mock,
)


class TestConversationRoundtrip:
    """对话完整流程测试：audio → ASR → LLM → TTS → response。"""

    def test_basic_conversation(self, ws_client, mock_asr_engine, mock_llm_client):
        """发送音频 → 收到完整响应序列。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["你好", "！", "[mood:happy]"])

        with ws_client() as ws:
            # 发送音频
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 等待响应
            ws.receive_all_available(timeout=3.0)

            # 验证消息序列
            sequence = ws.get_message_sequence()
            assert "tts_start" in sequence
            assert "text" in sequence
            assert "tts_end" in sequence

            # 验证顺序：tts_start 在 tts_end 之前
            assert sequence.index("tts_start") < sequence.index("tts_end")

            # 验证收到 PCM 帧
            assert_has_binary_frames(ws.received_bytes, min_count=1)

    def test_text_message_contains_mood(self, ws_client, mock_asr_engine, mock_llm_client):
        """text 消息应包含 mood 字段。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["好的", "[mood:happy]"])

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            ws.receive_all_available(timeout=3.0)

            text_msgs = ws.get_messages_by_type("text")
            assert len(text_msgs) > 0
            # 最后的 text 消息应包含 mood
            last_text = text_msgs[-1]
            assert "mood" in last_text

    def test_empty_audio_vad_no_speech(self, ws_client, mock_asr_engine):
        """VAD 检测无语音时不应触发 LLM/TTS。"""
        mock_asr_engine.vad_has_speech = lambda audio: False

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 验证无 TTS 响应（使用 ping/pong 确认连接有效）
            ws.verify_no_tts_response()

    def test_asr_empty_transcription(self, ws_client, mock_asr_engine):
        """ASR 返回空文本时不应触发 LLM。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="")

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 验证无 TTS 响应
            ws.verify_no_tts_response()

    def test_multiple_sentences_multiple_tts(self, ws_client, mock_asr_engine, mock_llm_client):
        """多句话应触发多次 TTS。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        # 两句话
        mock_llm_client.chat_stream = create_llm_stream_mock([
            "你好。",
            "很高兴见到你！",
            "[mood:happy]"
        ])

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            ws.receive_all_available(timeout=3.0)

            # 应收到多个 PCM 帧（每句 2 帧）
            assert_has_binary_frames(ws.received_bytes, min_count=2)


class TestEmotionSystem:
    """情绪系统测试 — 8 种情绪映射完整验证。"""

    @pytest.mark.parametrize("emotion", [
        "happy", "sad", "thinking", "angry",
        "sleepy", "surprised", "tsundere", "neutral"
    ])
    def test_emotion_extraction(self, ws_client, mock_asr_engine, mock_llm_client, emotion):
        """8 种情绪应能正确提取。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="测试")
        mock_llm_client.chat_stream = create_llm_stream_mock([
            f"回复内容[mood:{emotion}]"
        ])

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.receive_all_available(timeout=3.0)

            text_msgs = ws.get_messages_by_type("text")
            assert len(text_msgs) > 0, "Should have at least one text message"
            last_text = text_msgs[-1]

            # 验证 mood 值正确
            assert last_text["mood"] == emotion, \
                f"Expected mood={emotion}, got {last_text['mood']}"

            # 验证 [mood:xxx] 标签已从 content 中移除
            assert f"[mood:{emotion}]" not in last_text["content"], \
                f"Mood tag should be removed from content: {last_text['content']}"

    def test_invalid_mood_fallback_to_neutral(self, ws_client, mock_asr_engine, mock_llm_client):
        """无效 mood 标签应回退为 neutral。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="测试")
        mock_llm_client.chat_stream = create_llm_stream_mock([
            "回复[mood:invalid_emotion]"
        ])

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.receive_all_available(timeout=3.0)

            text_msgs = ws.get_messages_by_type("text")
            assert len(text_msgs) > 0
            # 无效情绪应回退到 neutral
            assert text_msgs[-1]["mood"] == "neutral"

    def test_no_mood_tag_defaults_to_neutral(self, ws_client, mock_asr_engine, mock_llm_client):
        """无 mood 标签时默认 neutral。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="测试")
        mock_llm_client.chat_stream = create_llm_stream_mock([
            "这是没有情绪标签的回复"
        ])

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.receive_all_available(timeout=3.0)

            text_msgs = ws.get_messages_by_type("text")
            assert len(text_msgs) > 0
            # 无标签默认 neutral
            assert text_msgs[-1]["mood"] == "neutral"

    def test_multiple_mood_tags_uses_last(self, ws_client, mock_asr_engine, mock_llm_client):
        """多个 mood 标签时应使用最后一个。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="测试")
        mock_llm_client.chat_stream = create_llm_stream_mock([
            "[mood:sad]开始[mood:angry]中间[mood:happy]结尾"
        ])

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.receive_all_available(timeout=3.0)

            text_msgs = ws.get_messages_by_type("text")
            assert len(text_msgs) > 0
            # 应使用最后一个 mood 标签 (happy)
            assert text_msgs[-1]["mood"] == "happy"
            # 所有标签都应被移除
            content = text_msgs[-1]["content"]
            assert "[mood:" not in content

    def test_mood_in_tts_start(self, ws_client, mock_asr_engine, mock_llm_client):
        """tts_start 消息应包含初始 mood。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="测试")
        mock_llm_client.chat_stream = create_llm_stream_mock([
            "回复[mood:surprised]"
        ])

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.receive_all_available(timeout=3.0)

            tts_start_msgs = ws.get_messages_by_type("tts_start")
            assert len(tts_start_msgs) > 0, "Should have tts_start message"
            # tts_start 应包含 mood 字段
            assert "mood" in tts_start_msgs[0]


class TestMultiTurnConversation:
    """多轮对话测试。"""

    def test_three_turn_conversation(self, ws_client, mock_asr_engine, mock_llm_client):
        """3 轮对话应正常完成。"""
        turns = ["第一句", "第二句", "第三句"]
        turn_idx = [0]

        async def transcribe_by_turn(audio):
            result = turns[turn_idx[0] % len(turns)]
            turn_idx[0] += 1
            return result

        mock_asr_engine.transcribe = transcribe_by_turn
        mock_llm_client.chat_stream = create_llm_stream_mock(["回复", "[mood:happy]"])

        with ws_client() as ws:
            for i in range(3):
                ws.clear()
                ws.send_audio_start()
                ws.send_bytes(b"\x00" * 1024)
                ws.send_audio_end()

                # 等待本轮完成
                ws.wait_for_message_type("tts_end", timeout=3.0)

            # 3 轮都应有 tts_end
            tts_ends = [m for m in ws.received_json if m.get("type") == "tts_end"]
            assert len(tts_ends) >= 1  # 至少最后一轮

    def test_conversation_state_returns_to_idle(self, ws_client, mock_asr_engine):
        """对话结束后应回到 IDLE 状态，可开始新对话。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")

        with ws_client() as ws:
            # 第一轮
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.wait_for_message_type("tts_end", timeout=3.0)

            ws.clear()

            # 第二轮应能正常开始
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            ws.receive_all_available(timeout=3.0)

            # 第二轮也应有响应
            assert "tts_start" in ws.get_message_sequence()
