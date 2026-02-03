"""WebSocket endpoint + 消息路由分发。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect

from wallace.ws.protocol import PongMessage, SessionRestoreMessage, parse_esp32_message
from wallace.ws.session import Session

if TYPE_CHECKING:
    from wallace.pipeline.orchestrator import Orchestrator
    from wallace.sensor import SensorProcessor
    from wallace.smarthome.mqtt import MQTTManager
    from wallace.wakeword import WakewordVerifier

logger = logging.getLogger(__name__)

# 心跳超时 (秒)
HEARTBEAT_TIMEOUT = 90


class WebSocketHandler:
    """处理单个 WebSocket 连接的消息路由。"""

    def __init__(
        self,
        sessions: dict[str, Session],
        orchestrator: Orchestrator,
        sensor: SensorProcessor,
        wakeword: WakewordVerifier,
        mqtt: MQTTManager,
    ) -> None:
        self._sessions = sessions
        self._orchestrator = orchestrator
        self._sensor = sensor
        self._wakeword = wakeword
        self._mqtt = mqtt

    async def handle_connection(self, ws: WebSocket, user_id: str) -> None:
        """处理完整的 WebSocket 连接生命周期。"""
        await ws.accept()
        session = Session(user_id, ws)

        # 重连检查：是否已有同 user_id 的 session
        old = self._sessions.get(user_id)
        if old is not None:
            # 恢复状态
            session.personality = old.personality
            session.treehouse_mode = old.treehouse_mode
            session.tts_backend = old.tts_backend
            session.memory = old.memory
            # 清理旧 session
            await self._orchestrator.cancel_pipeline(old)

        self._sessions[user_id] = session

        # 重连时发送 session_restore
        if old is not None:
            await ws.send_text(
                SessionRestoreMessage(
                    personality=session.personality,
                    treehouse=session.treehouse_mode,
                    tts_backend=session.tts_backend,
                ).model_dump_json()
            )

        # 启动心跳监控
        heartbeat_task = asyncio.create_task(self._heartbeat_monitor(session))

        try:
            await self._message_loop(session)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: %s", user_id)
        except Exception:
            logger.exception("WebSocket error: %s", user_id)
        finally:
            heartbeat_task.cancel()
            await self._orchestrator.cancel_pipeline(session)
            # TODO: flush memory
            self._sessions.pop(user_id, None)

    async def _message_loop(self, session: Session) -> None:
        """消息接收主循环。"""
        while True:
            msg = await session.ws.receive()

            if msg["type"] == "websocket.disconnect":
                break

            if msg["type"] == "websocket.receive":
                if "bytes" in msg and msg["bytes"]:
                    # 二进制帧 → 音频
                    session.append_audio(msg["bytes"])
                elif "text" in msg and msg["text"]:
                    await self._route_json(session, msg["text"])

    async def _route_json(self, session: Session, raw: str) -> None:
        """解析 JSON 并路由到处理器。"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from %s: %s", session.user_id, raw[:100])
            return

        try:
            parse_esp32_message(data)  # validate message format
        except ValueError as e:
            logger.warning("Unknown message from %s: %s", session.user_id, e)
            return

        msg_type = data.get("type")

        if msg_type == "ping":
            session.update_heartbeat()
            await session.ws.send_text(PongMessage().model_dump_json())

        elif msg_type == "audio_start":
            await self._orchestrator.handle_audio_start(session)

        elif msg_type == "audio_end":
            await self._orchestrator.handle_audio_end(session)

        elif msg_type == "wakeword_verify":
            result = await self._wakeword.verify(data["audio"])
            from wallace.ws.protocol import WakewordResultMessage

            await session.ws.send_text(
                WakewordResultMessage(confirmed=result).model_dump_json()
            )
            if result:
                session.wakeword_confirmed.set()
            else:
                session.wakeword_confirmed.clear()

        elif msg_type == "sensor":
            self._sensor.update_cache(session, data)
            alerts = self._sensor.check_alerts(session)
            for alert_type, suggestion in alerts:
                from wallace.ws.protocol import SensorAlertMessage

                await session.ws.send_text(
                    SensorAlertMessage(alert=alert_type, suggestion=suggestion).model_dump_json()
                )

        elif msg_type == "proximity":
            self._sensor.update_proximity(session, data)

        elif msg_type == "device_state":
            pass  # 更新连接状态缓存（暂存 session 属性）

        elif msg_type == "event":
            await self._handle_event(session, data)

        elif msg_type == "local_cmd":
            success, message = await self._mqtt.execute_command(data["action"])
            from wallace.ws.protocol import CommandResultMessage

            await session.ws.send_text(
                CommandResultMessage(
                    action=data["action"], success=success, message=message
                ).model_dump_json()
            )

        elif msg_type == "config":
            if "tts_backend" in data:
                session.tts_backend = data["tts_backend"]

    async def _handle_event(self, session: Session, data: dict) -> None:
        event = data.get("event")
        value = data.get("value")

        if event == "personality_switch":

            session.personality = value
            session.chat_history.clear()

        elif event == "treehouse_mode":
            session.treehouse_mode = bool(value)

        elif event == "shake":
            # 异步触发冷知识生成，跟踪任务以便后续取消
            task = asyncio.create_task(self._orchestrator.push_random_fact(session))
            session.random_fact_task = task

        elif event == "touch":
            pass  # optional: log interaction

    async def _heartbeat_monitor(self, session: Session) -> None:
        """监控心跳超时。"""
        try:
            while True:
                await asyncio.sleep(30)
                elapsed = time.monotonic() - session.last_heartbeat
                if elapsed > HEARTBEAT_TIMEOUT:
                    logger.warning("Heartbeat timeout for %s (%.0fs)", session.user_id, elapsed)
                    await session.ws.close()
                    break
        except asyncio.CancelledError:
            pass
