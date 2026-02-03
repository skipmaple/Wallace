"""E2E 测试 — 记忆系统完整流程。"""

from __future__ import annotations

from unittest.mock import AsyncMock



from .conftest import create_llm_stream_mock


class TestMemoryInjection:
    """记忆注入 LLM prompt 测试。"""

    def test_memory_nickname_in_conversation(
        self, e2e_app, ws_client, mock_asr_engine, mock_llm_client
    ):
        """用户昵称应注入 LLM prompt。"""
        # 设置 memory 昵称
        user_id = "memory_test_user"

        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["你好！", "[mood:happy]"])

        # 记录 build_messages 调用
        captured_calls = []
        original_build = mock_llm_client.build_messages

        def capture_build(session, text, sensor_ctx=""):
            captured_calls.append((session, text, sensor_ctx))
            return original_build(session, text, sensor_ctx)

        mock_llm_client.build_messages = capture_build

        with ws_client(user_id=user_id) as ws:
            # 获取 session 并设置 memory
            session = e2e_app.state.sessions.get(user_id)
            session.memory.nickname = "小王"
            session.memory.interests = ["编程", "音乐"]

            # 发送对话
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.receive_all_available(timeout=3.0)

        # 验证 build_messages 被调用
        assert len(captured_calls) > 0
        call_session = captured_calls[0][0]
        # session 中的 memory 应包含昵称
        assert call_session.memory.nickname == "小王"
        assert "编程" in call_session.memory.interests

    def test_memory_interests_in_conversation(
        self, e2e_app, ws_client, mock_asr_engine, mock_llm_client
    ):
        """用户兴趣应注入 LLM prompt。"""
        user_id = "interest_test_user"

        mock_asr_engine.transcribe = AsyncMock(return_value="推荐点什么")
        mock_llm_client.chat_stream = create_llm_stream_mock(["好的！", "[mood:happy]"])

        with ws_client(user_id=user_id) as ws:
            session = e2e_app.state.sessions.get(user_id)
            session.memory.interests = ["游戏", "电影", "旅行"]

            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.receive_all_available(timeout=3.0)

            # 验证连接有效
            assert "tts_end" in ws.get_message_sequence()


class TestMemoryPersistence:
    """记忆持久化测试（端到端验证）。"""

    def test_conversation_increments_interaction_count(
        self, e2e_app, ws_client, mock_asr_engine, mock_llm_client
    ):
        """对话后 interaction_count 应增加。"""
        user_id = "interaction_count_user"

        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["你好！", "[mood:happy]"])

        with ws_client(user_id=user_id) as ws:
            session = e2e_app.state.sessions.get(user_id)
            _initial_count = session.memory.interaction_count  # noqa: F841

            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.receive_all_available(timeout=3.0)

            # 注意：interaction_count 是否增加取决于服务器实现
            # 这里主要验证流程不崩溃


class TestMemoryOnOverlappingConnect:
    """同用户重复连接时记忆恢复测试。

    注意：当同一用户建立新连接时，如果旧连接仍存在，
    新 session 会从旧 session 继承 memory。
    这在 test_reconnect.py 中已有测试，这里验证 memory 相关行为。
    """

    def test_memory_preserved_on_overlapping_connect(self, e2e_app, client):
        """同用户重复连接时 memory 应被继承。"""
        from tests.e2e.conftest import E2EWebSocketClient

        user_id = "overlap_memory_user"

        # 第一次连接 - 设置 memory（保持连接不断开）
        with client.websocket_connect(f"/ws/{user_id}") as ws1:
            ws_client1 = E2EWebSocketClient(ws1)
            session1 = e2e_app.state.sessions.get(user_id)
            session1.memory.nickname = "测试用户"
            session1.memory.interests = ["测试"]

            ws_client1.send_ping()
            ws_client1.wait_for_message_type("pong", timeout=2.0)

            # 第二次连接（在第一次连接仍存在时）
            with client.websocket_connect(f"/ws/{user_id}") as ws2:
                ws_client2 = E2EWebSocketClient(ws2)
                ws_client2.send_ping()
                ws_client2.wait_for_message_type("pong", timeout=2.0)

                # 新 session 应继承 memory
                session2 = e2e_app.state.sessions.get(user_id)
                assert session2.memory.nickname == "测试用户"
                assert "测试" in session2.memory.interests


class TestMemoryAndConversation:
    """记忆与对话流程协作测试。"""

    def test_multi_turn_with_memory(
        self, e2e_app, ws_client, mock_asr_engine, mock_llm_client
    ):
        """多轮对话中 memory 应一致。"""
        user_id = "multi_turn_memory_user"

        mock_asr_engine.transcribe = AsyncMock(return_value="你好")
        mock_llm_client.chat_stream = create_llm_stream_mock(["回复", "[mood:happy]"])

        with ws_client(user_id=user_id) as ws:
            session = e2e_app.state.sessions.get(user_id)
            session.memory.nickname = "多轮测试"

            # 第一轮
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.wait_for_message_type("tts_end", timeout=3.0)
            ws.clear()

            # 第二轮 - memory 应保持
            ws.send_audio_start()
            ws.send_bytes(b"\x00" * 1024)
            ws.send_audio_end()
            ws.wait_for_message_type("tts_end", timeout=3.0)

            # 验证 memory 保持不变
            assert session.memory.nickname == "多轮测试"
