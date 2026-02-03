"""LLM 客户端 — Ollama HTTP API 流式对话。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import httpx


if TYPE_CHECKING:
    from wallace.config import LLMConfig
    from wallace.ws.session import Session

logger = logging.getLogger(__name__)

_PERSONALITY_PROMPTS: dict[str, str] = {
    "normal": "你是 Wallace，一个温暖可爱的桌面 AI 机器人。你说话简洁有趣，关心主人。",
    "cool": "你是 Wallace，一个高冷寡言的 AI 机器人。你回答简短，偶尔毒舌但其实很关心主人。",
    "talkative": "你是 Wallace，一个话痨 AI 机器人。你滔滔不绝，什么话题都能聊，非常热情。",
    "tsundere": "你是 Wallace，一个傲娇的 AI 机器人。你嘴上说不在乎，但行动上很关心主人。经常用「才不是」「哼」等口癖。",
}

_MOOD_INSTRUCTION = (
    "\n在回复最末尾加上情绪标签，格式为 [mood:xxx]，"
    "可选值: happy, sad, thinking, angry, sleepy, surprised, tsundere, neutral。"
)


class LLMClient:
    """Ollama 流式对话客户端。"""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._healthy: bool = False

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url, timeout=httpx.Timeout(60.0)
        )
        self._healthy = await self.health_check()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    async def health_check(self) -> bool:
        """Ping Ollama /api/tags 检查可用性。"""
        if not self._client:
            return False
        try:
            resp = await self._client.get("/api/tags", timeout=5.0)
            self._healthy = resp.status_code == 200
        except (httpx.HTTPError, Exception):
            self._healthy = False
        return self._healthy

    def build_messages(
        self,
        session: Session,
        user_text: str,
        sensor_context: str = "",
    ) -> list[dict[str, str]]:
        """组装 LLM messages（system + history + user）。"""
        system_prompt = _PERSONALITY_PROMPTS.get(session.personality, _PERSONALITY_PROMPTS["normal"])
        system_prompt += _MOOD_INSTRUCTION

        # 记忆摘要
        mem = session.memory
        if mem.nickname:
            system_prompt += f"\n主人叫{mem.nickname}。"
        if mem.interests:
            system_prompt += f"\n主人的兴趣：{'、'.join(mem.interests)}。"

        # 传感器上下文
        if sensor_context:
            system_prompt += f"\n{sensor_context}"

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(session.chat_history[-self.config.max_history_turns * 2 :])
        messages.append({"role": "user", "content": user_text})
        return messages

    async def chat_stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        """流式调用 Ollama /api/chat，逐 token yield。"""
        if not self._client:
            raise RuntimeError("LLM client not started")

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        async with self._client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                import json

                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break

    def switch_personality(self, session: Session, personality: str) -> None:
        """切换人格并清空对话历史。"""
        session.personality = personality
        session.chat_history.clear()
