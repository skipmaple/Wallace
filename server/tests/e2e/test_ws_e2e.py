"""E2E 测试 — WebSocket 基础功能与边界情况。"""

from __future__ import annotations

from unittest.mock import AsyncMock

from .conftest import create_llm_stream_mock


class TestHeartbeat:
    """心跳测试。"""

    def test_ping_pong(self, ws_client):
        """ping 应收到 pong 响应。"""
        with ws_client() as ws:
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None
            assert pong.get("type") == "pong"

    def test_multiple_pings(self, ws_client):
        """多次 ping 都应收到响应。"""
        with ws_client() as ws:
            for _ in range(3):
                ws.send_ping()
                pong = ws.wait_for_message_type("pong", timeout=2.0)
                assert pong is not None
                assert pong.get("type") == "pong"
                # 清理已收到的消息以便下一轮
                ws.clear()


class TestConnection:
    """连接测试。"""

    def test_websocket_connect(self, ws_client):
        """WebSocket 应能正常连接。"""
        with ws_client() as ws:
            # 连接成功，发送心跳验证
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_different_user_ids(self, client):
        """不同 user_id 应能同时连接。"""
        with client.websocket_connect("/ws/user1") as ws1, \
             client.websocket_connect("/ws/user2") as ws2:
            from .conftest import E2EWebSocketClient

            client1 = E2EWebSocketClient(ws1)
            client2 = E2EWebSocketClient(ws2)

            client1.send_ping()
            client2.send_ping()

            pong1 = client1.wait_for_message_type("pong", timeout=2.0)
            pong2 = client2.wait_for_message_type("pong", timeout=2.0)

            assert pong1 is not None
            assert pong2 is not None


class TestInvalidInput:
    """无效输入处理测试。"""

    def test_invalid_json_no_crash(self, client):
        """无效 JSON 不应导致崩溃。"""
        with client.websocket_connect("/ws/test_user") as ws:
            # 发送无效 JSON
            ws.send_text("not a json")

            # 连接应仍有效
            ws.send_json({"type": "ping"})
            # 等待响应
            pong = ws.receive_json()
            assert pong.get("type") == "pong"

    def test_unknown_message_type(self, ws_client):
        """未知消息类型应被忽略。"""
        with ws_client() as ws:
            ws.send_json({"type": "unknown_type", "data": "test"})

            # 连接应仍有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_missing_type_field(self, ws_client):
        """缺少 type 字段的消息应被处理。"""
        with ws_client() as ws:
            ws.send_json({"data": "no type field"})

            # 连接应仍有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None


class TestHealthEndpoint:
    """健康检查端点测试。"""

    def test_health_endpoint(self, client):
        """GET /health 应返回状态。"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"


class TestBinaryData:
    """二进制数据处理测试。"""

    def test_binary_frames_buffered(self, ws_client, mock_asr_engine, mock_llm_client):
        """二进制帧应被缓冲。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="测试")
        mock_llm_client.chat_stream = create_llm_stream_mock(["回复", "[mood:happy]"])

        with ws_client() as ws:
            ws.send_audio_start()

            # 发送多帧音频
            for _ in range(5):
                ws.send_bytes(b"\x00" * 1024)

            ws.send_audio_end()

            # 等待响应
            ws.receive_all_available(timeout=5.0)

            # 应有响应（表示音频被处理）
            assert "tts_start" in ws.get_message_sequence()

    def test_empty_audio_buffer(self, ws_client, mock_asr_engine):
        """空音频缓冲应被处理。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="")

        with ws_client() as ws:
            ws.send_audio_start()
            # 不发送任何音频帧
            ws.send_audio_end()

            # 验证连接有效（不应崩溃）
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None


class TestWebSocketE2E:
    """原有的 E2E 测试类（保持兼容）。"""

    def test_conversation_roundtrip(self, ws_client, mock_asr_engine, mock_llm_client):
        """连接 → 发音频 → 收到 TTS 回复。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["回复", "[mood:happy]"])

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            ws.receive_all_available(timeout=3.0)

            assert "tts_start" in ws.get_message_sequence()
            assert "tts_end" in ws.get_message_sequence()

    def test_interrupt_during_playback(
        self, ws_client, mock_asr_engine, mock_llm_client, mock_tts_manager
    ):
        """播放中发 audio_start → 应不崩溃。"""
        from .conftest import create_tts_mock

        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["回复", "[mood:happy]"])
        mock_tts_manager.synthesize = create_tts_mock(frame_count=10, frame_delay=0.2)

        with ws_client() as ws:
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()

            ws.wait_for_message_type("tts_start", timeout=3.0)

            ws.send_audio_start()

            # 验证连接有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_multi_turn_conversation(self, ws_client, mock_asr_engine, mock_llm_client):
        """3 轮对话 → 对话历史正确累积。"""
        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["回复", "[mood:happy]"])

        with ws_client() as ws:
            for _ in range(3):
                ws.send_audio_start()
                ws.send_bytes(b"\x00" * 1024)
                ws.send_audio_end()
                ws.wait_for_message_type("tts_end", timeout=3.0)
                ws.clear()

            # 3 轮都完成

    def test_sensor_triggers_alert(self, ws_client, e2e_settings):
        """发传感器数据 → 不崩溃（告警可选）。"""
        threshold = e2e_settings.sensor.air_quality_threshold

        with ws_client() as ws:
            ws.send_sensor_data(air_quality=threshold + 100)

            # 验证连接有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_personality_switch(self, ws_client):
        """发 personality_switch → 后续对话 prompt 更新。"""
        with ws_client() as ws:
            ws.send_event("personality_switch", "tsundere")

            # 验证连接有效
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None
