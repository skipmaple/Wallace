"""E2E 测试 — 重连与会话恢复。"""

from __future__ import annotations



class TestSessionRestore:
    """会话恢复测试。

    根据 architecture.md §重连机制：
    ESP32 断连后重连时，服务端发送 session_restore 消息同步当前状态。
    """

    def test_reconnect_same_user(self, ws_client):
        """同一用户重连应能正常连接。"""
        user_id = "reconnect_test_user"

        # 第一次连接
        with ws_client(user_id=user_id) as ws:
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

        # 第二次连接（重连）
        with ws_client(user_id=user_id) as ws:
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_reconnect_sends_session_restore(self, ws_client):
        """重连时服务端必须发送 session_restore 消息。"""
        user_id = "session_restore_user"

        # 第一次连接 - 设置一些状态
        with ws_client(user_id=user_id) as ws:
            ws.send_event("personality_switch", "tsundere")
            ws.send_event("treehouse_mode", True)
            ws.send_json({"type": "config", "tts_backend": "cosyvoice"})
            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

        # 重连 - 必须收到 session_restore
        with ws_client(user_id=user_id) as ws:
            # session_restore 应在连接建立后立即发送
            restore = ws.wait_for_message_type("session_restore", timeout=2.0)
            assert restore is not None, "重连时必须发送 session_restore 消息"
            assert restore.get("personality") == "tsundere"
            assert restore.get("treehouse") is True
            assert restore.get("tts_backend") == "cosyvoice"

    def test_reconnect_restores_personality(self, ws_client):
        """重连后人格设置必须恢复。"""
        user_id = "personality_restore_user"

        # 第一次连接 - 设置人格
        with ws_client(user_id=user_id) as ws:
            ws.send_event("personality_switch", "cool")
            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

        # 重连
        with ws_client(user_id=user_id) as ws:
            restore = ws.wait_for_message_type("session_restore", timeout=2.0)
            assert restore is not None, "重连必须发送 session_restore"
            assert restore.get("personality") == "cool", "人格设置必须恢复"

    def test_reconnect_restores_treehouse_mode(self, ws_client):
        """重连后树洞模式设置必须恢复。"""
        user_id = "treehouse_restore_user"

        # 第一次连接 - 开启树洞模式
        with ws_client(user_id=user_id) as ws:
            ws.send_event("treehouse_mode", True)
            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

        # 重连
        with ws_client(user_id=user_id) as ws:
            restore = ws.wait_for_message_type("session_restore", timeout=2.0)
            assert restore is not None, "重连必须发送 session_restore"
            assert restore.get("treehouse") is True, "树洞模式设置必须恢复"

    def test_reconnect_restores_tts_backend(self, ws_client):
        """重连后 TTS 后端设置必须恢复。"""
        user_id = "tts_restore_user"

        # 第一次连接 - 切换 TTS 后端
        with ws_client(user_id=user_id) as ws:
            ws.send_json({"type": "config", "tts_backend": "cosyvoice"})
            ws.send_ping()
            ws.wait_for_message_type("pong", timeout=2.0)

        # 重连
        with ws_client(user_id=user_id) as ws:
            restore = ws.wait_for_message_type("session_restore", timeout=2.0)
            assert restore is not None, "重连必须发送 session_restore"
            assert restore.get("tts_backend") == "cosyvoice", "TTS 后端设置必须恢复"

    def test_first_connect_no_session_restore(self, ws_client):
        """首次连接不应发送 session_restore。"""
        import uuid
        user_id = f"new_user_{uuid.uuid4().hex[:8]}"

        with ws_client(user_id=user_id) as ws:
            ws.send_ping()
            pong = ws.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

            # 首次连接不应有 session_restore
            restore_msgs = ws.get_messages_by_type("session_restore")
            assert len(restore_msgs) == 0, "首次连接不应发送 session_restore"


class TestMultipleUsers:
    """多用户测试。"""

    def test_different_users_independent(self, client):
        """不同用户应有独立会话。"""
        # 同时连接两个用户
        with client.websocket_connect("/ws/user_a") as ws_a, \
             client.websocket_connect("/ws/user_b") as ws_b:

            from .conftest import E2EWebSocketClient
            client_a = E2EWebSocketClient(ws_a)
            client_b = E2EWebSocketClient(ws_b)

            # 用户 A 切换人格
            client_a.send_event("personality_switch", "cool")

            # 用户 B 不应受影响
            client_b.send_ping()
            pong = client_b.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None

    def test_user_disconnect_no_affect_others(self, client):
        """一个用户断开不应影响其他用户。"""
        with client.websocket_connect("/ws/user_stay") as ws_stay:
            from .conftest import E2EWebSocketClient
            client_stay = E2EWebSocketClient(ws_stay)

            # 另一个用户连接后断开
            with client.websocket_connect("/ws/user_leave"):
                pass  # 立即断开

            # 留下的用户应仍能正常工作
            client_stay.send_ping()
            pong = client_stay.wait_for_message_type("pong", timeout=2.0)
            assert pong is not None
