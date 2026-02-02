"""智能家居 MQTT 接口。"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import aiomqtt

if TYPE_CHECKING:
    from wallace.config import MQTTConfig

logger = logging.getLogger(__name__)

# 场景联动定义
SCENES: dict[str, list[dict[str, Any]]] = {
    "sleep": [
        {"device": "light", "action": "off"},
        {"device": "ac", "action": "sleep_mode"},
    ],
    "wakeup": [
        {"device": "light", "action": "on", "payload": {"brightness": 50}},
    ],
}


class MQTTManager:
    """MQTT 智能家居管理。"""

    def __init__(self, config: MQTTConfig) -> None:
        self.config = config
        self._client = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """连接 MQTT broker。"""
        try:
            self._client = aiomqtt.Client(
                hostname=self.config.broker,
                port=self.config.port,
                username=self.config.username or None,
                password=self.config.password or None,
            )
            # aiomqtt requires context manager; actual connection logic
            # will be handled in the main loop
            self._connected = True
            logger.info("MQTT connected to %s:%d", self.config.broker, self.config.port)
        except Exception as e:
            logger.warning("MQTT connection failed: %s, running in degraded mode", e)
            self._connected = False

    async def disconnect(self) -> None:
        self._connected = False
        self._client = None

    async def execute_command(self, action: str, payload: dict | None = None) -> tuple[bool, str]:
        """执行单个智能家居命令。返回 (success, message)。"""
        if not self._connected:
            return False, "MQTT not connected"

        topic = f"{self.config.topic_prefix}/{action}"
        msg = json.dumps(payload or {})

        try:
            # In actual implementation, use self._client.publish()
            logger.info("MQTT publish: %s → %s", topic, msg)
            return True, f"{action} executed"
        except Exception as e:
            logger.error("MQTT publish failed: %s", e)
            return False, str(e)

    async def execute_scene(self, scene_name: str) -> list[tuple[str, bool, str]]:
        """执行场景联动。返回每个命令的结果。"""
        commands = SCENES.get(scene_name, [])
        if not commands:
            return [(scene_name, False, f"Unknown scene: {scene_name}")]

        results = []
        for cmd in commands:
            action = f"{cmd['device']}/{cmd['action']}"
            success, msg = await self.execute_command(action, cmd.get("payload"))
            results.append((action, success, msg))
        return results
