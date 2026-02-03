"""E2E 测试 — 唤醒词二阶段确认流程。"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock



class TestWakewordVerification:
    """唤醒词二阶段确认测试。"""

    def test_wakeword_confirm_success(self, ws_client, mock_wakeword):
        """唤醒词确认通过。"""
        mock_wakeword.verify = AsyncMock(return_value=True)

        with ws_client() as ws:
            ws.send_json({
                "type": "wakeword_verify",
                "audio": base64.b64encode(b"\x00" * 1024).decode()
            })

            result = ws.wait_for_message_type("wakeword_result", timeout=3.0)
            assert result is not None
            assert result["confirmed"] is True

    def test_wakeword_confirm_failed(self, ws_client, mock_wakeword):
        """唤醒词确认失败。"""
        mock_wakeword.verify = AsyncMock(return_value=False)

        with ws_client() as ws:
            ws.send_json({
                "type": "wakeword_verify",
                "audio": base64.b64encode(b"\x00" * 1024).decode()
            })

            result = ws.wait_for_message_type("wakeword_result", timeout=3.0)
            assert result is not None
            assert result["confirmed"] is False

    def test_wakeword_invalid_audio_format(self, ws_client):
        """无效的音频格式不应导致崩溃。"""
        with ws_client() as ws:
            ws.send_json({
                "type": "wakeword_verify",
                "audio": "not-valid-base64!!!"
            })

            # 连接应仍然有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_wakeword_missing_audio_field(self, ws_client):
        """缺少 audio 字段不应导致崩溃。"""
        with ws_client() as ws:
            ws.send_json({"type": "wakeword_verify"})

            # 连接应仍然有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None


class TestWakewordAndConversation:
    """唤醒词与对话流程的协作测试。"""

    def test_wakeword_then_conversation(
        self, ws_client, mock_wakeword, mock_asr_engine, mock_llm_client
    ):
        """唤醒词确认后应能正常对话。"""
        mock_wakeword.verify = AsyncMock(return_value=True)
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")

        with ws_client() as ws:
            # 1. 先确认唤醒词
            ws.send_json({
                "type": "wakeword_verify",
                "audio": base64.b64encode(b"\x00" * 1024).decode()
            })
            result = ws.wait_for_message_type("wakeword_result", timeout=3.0)
            assert result["confirmed"] is True

            ws.clear()

            # 2. 然后正常对话
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            ws.receive_all_available(timeout=3.0)

            # 应有 TTS 响应
            assert "tts_start" in ws.get_message_sequence()
            assert "tts_end" in ws.get_message_sequence()
