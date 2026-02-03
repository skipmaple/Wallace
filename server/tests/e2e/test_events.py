"""E2E 测试 — 事件处理（人格切换、树洞模式、本地命令等）。"""

from __future__ import annotations

from unittest.mock import AsyncMock


from .conftest import create_llm_stream_mock


class TestPersonalitySwitch:
    """人格切换测试。"""

    def test_personality_switch_event(self, ws_client, mock_llm_client):
        """发送 personality_switch 事件应被处理。"""
        with ws_client() as ws:
            # 切换到傲娇模式
            ws.send_event("personality_switch", "tsundere")

            # 验证不崩溃，连接仍有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_all_personality_modes(self, ws_client):
        """所有人格模式都能切换。"""
        personalities = ["normal", "cool", "talkative", "tsundere"]

        with ws_client() as ws:
            for personality in personalities:
                ws.send_event("personality_switch", personality)

            # 验证连接有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_personality_affects_conversation(
        self, ws_client, mock_asr_engine, mock_llm_client
    ):
        """切换人格后对话应正常工作。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["哼！", "[mood:tsundere]"])

        with ws_client() as ws:
            # 切换人格
            ws.send_event("personality_switch", "tsundere")

            # 进行对话
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            ws.receive_all_available(timeout=3.0)

            # 应有响应
            assert "tts_start" in ws.get_message_sequence()


class TestTreehouseMode:
    """树洞模式测试（只听不说）。"""

    def test_treehouse_mode_no_response(self, ws_client, mock_asr_engine):
        """树洞模式下不应有 TTS 响应。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="我想说的话")

        with ws_client() as ws:
            # 开启树洞模式
            ws.send_event("treehouse_mode", True)

            # 发送音频
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 验证无 TTS 响应
            ws.verify_no_tts_response()

    def test_treehouse_mode_no_llm_call(self, ws_client, mock_asr_engine, mock_llm_client):
        """树洞模式下不应调用 LLM。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="秘密内容")
        llm_called = []

        async def track_llm(messages):
            llm_called.append(messages)
            for token in ["不应看到", "[mood:happy]"]:
                yield token

        mock_llm_client.chat_stream = track_llm

        with ws_client() as ws:
            # 开启树洞模式
            ws.send_event("treehouse_mode", True)

            # 发送音频
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 验证无 TTS 响应
            ws.verify_no_tts_response()

        # LLM 不应被调用
        assert len(llm_called) == 0, "LLM should not be called in treehouse mode"

    def test_treehouse_mode_toggle(self, ws_client, mock_asr_engine, mock_llm_client):
        """树洞模式可以开关。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["回复", "[mood:happy]"])

        with ws_client() as ws:
            # 开启树洞模式
            ws.send_event("treehouse_mode", True)

            # 发送音频 - 不应有响应
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 验证无 TTS 响应
            ws.verify_no_tts_response()

            ws.clear()

            # 关闭树洞模式
            ws.send_event("treehouse_mode", False)

            # 再次发送音频 - 应有响应
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.receive_all_available(timeout=3.0)
            assert "tts_start" in ws.get_message_sequence()

    def test_treehouse_preserves_asr(self, ws_client, mock_asr_engine):
        """树洞模式仍应进行 ASR 转录。"""
        asr_called = []

        async def track_asr(audio):
            asr_called.append(audio)
            return "树洞内容"

        mock_asr_engine.transcribe = track_asr

        with ws_client() as ws:
            ws.send_event("treehouse_mode", True)

            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            ws.verify_no_tts_response()

        # ASR 应被调用
        assert len(asr_called) > 0, "ASR should still be called in treehouse mode"


class TestLocalCommands:
    """本地智能家居命令测试。"""

    def test_local_cmd_returns_result(self, ws_client, mock_mqtt_manager):
        """local_cmd 应返回 command_result。"""
        mock_mqtt_manager.execute_command = AsyncMock(return_value=(True, "灯已打开"))

        with ws_client() as ws:
            ws.send_local_cmd("light_on")

            result = ws.wait_for_message_type("command_result", timeout=2.0)
            assert result is not None
            assert result.get("action") == "light_on"
            assert result.get("success") is True

    def test_local_cmd_failure(self, ws_client, mock_mqtt_manager):
        """MQTT 执行失败应返回失败结果。"""
        mock_mqtt_manager.execute_command = AsyncMock(return_value=(False, "设备离线"))

        with ws_client() as ws:
            ws.send_local_cmd("light_on")

            result = ws.wait_for_message_type("command_result", timeout=2.0)
            assert result is not None
            assert result.get("success") is False

    def test_mqtt_disconnected_graceful_failure(self, ws_client, mock_mqtt_manager):
        """MQTT 未连接时应优雅失败。"""
        mock_mqtt_manager.is_connected = False
        mock_mqtt_manager.execute_command = AsyncMock(return_value=(False, "MQTT 未连接"))

        with ws_client() as ws:
            ws.send_local_cmd("light_on")

            result = ws.wait_for_message_type("command_result", timeout=2.0)
            # 应有结果或不崩溃
            if result:
                assert result.get("success") is False


class TestShakeEvent:
    """摇一摇事件测试。"""

    def test_shake_event_triggers_tts(
        self, ws_client, mock_llm_client, mock_asr_engine
    ):
        """摇一摇事件应触发冷知识 TTS 响应。"""
        mock_llm_client.chat_stream = create_llm_stream_mock([
            "你知道吗？",
            "蜂蜜永远不会变质！",
            "[mood:surprised]"
        ])

        with ws_client() as ws:
            ws.send_event("shake", None)

            # 等待 TTS 响应
            ws.receive_all_available(timeout=5.0)

            # 应有 TTS 输出
            sequence = ws.get_message_sequence()
            assert "tts_start" in sequence
            assert "tts_end" in sequence

            # 应有音频帧
            assert len(ws.received_bytes) > 0

            # text 消息应包含 mood
            text_msgs = ws.get_messages_by_type("text")
            assert len(text_msgs) > 0
            assert text_msgs[-1].get("mood") == "surprised"

    def test_shake_busy_ignored(self, ws_client, mock_llm_client, mock_asr_engine):
        """忙碌状态时 shake 应被忽略。"""
        # 先启动一个对话让状态非 IDLE
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock([
            "你好！",
            "[mood:happy]"
        ])

        with ws_client() as ws:
            # 先发送音频开始对话
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            # 等待 tts_start 说明正在处理
            ws.wait_for_message_type("tts_start", timeout=3.0)

            # 此时发送 shake 应被忽略
            ws.send_event("shake", None)

            # 等待对话完成
            ws.receive_all_available(timeout=5.0)

            # 验证连接有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None


class TestConfigChange:
    """配置变更测试。"""

    def test_tts_backend_switch(self, ws_client, mock_tts_manager):
        """切换 TTS 后端。"""
        with ws_client() as ws:
            ws.send_json({"type": "config", "tts_backend": "cosyvoice"})

            # 验证不崩溃
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None
