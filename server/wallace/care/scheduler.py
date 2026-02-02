"""主动关怀 — APScheduler 定时任务。"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from wallace.config import CareConfig, WeatherConfig
    from wallace.pipeline.llm import LLMClient
    from wallace.pipeline.tts import TTSManager
    from wallace.ws.session import Session

logger = logging.getLogger(__name__)


class CareScheduler:
    """管理所有主动关怀定时任务。"""

    def __init__(
        self,
        config: CareConfig,
        weather_config: WeatherConfig,
        sessions: dict[str, Session],
        llm: LLMClient,
        tts: TTSManager,
    ) -> None:
        self.config = config
        self.weather_config = weather_config
        self._sessions = sessions
        self._llm = llm
        self._tts = tts
        self._scheduler = None

    async def start(self) -> None:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self._scheduler = AsyncIOScheduler()

        # 久坐提醒
        self._scheduler.add_job(
            self._sedentary_reminder,
            "interval",
            hours=self.config.sedentary_interval_hours,
            id="sedentary",
        )

        # 早安
        h, m = self.config.morning_time.split(":")
        self._scheduler.add_job(
            self._morning_greeting,
            "cron",
            hour=int(h),
            minute=int(m),
            id="morning",
        )

        # 晚安
        h, m = self.config.evening_time.split(":")
        self._scheduler.add_job(
            self._evening_greeting,
            "cron",
            hour=int(h),
            minute=int(m),
            id="evening",
        )

        self._scheduler.start()
        logger.info("Care scheduler started")

    async def stop(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)

    async def _push_to_session(self, session: Session, prompt: str, mood: str) -> None:
        """向单个 session 推送关怀。含冲突处理和前置检查。"""
        # 前置检查：用户是否在旁边
        if not session.proximity_present:
            logger.debug("Skipping care push: user not present (%s)", session.user_id)
            return

        # 冲突处理：等待流水线完成
        try:
            acquired = await asyncio.wait_for(
                session.pipeline_lock.acquire(), timeout=self.config.push_timeout
            )
            if not acquired:
                return
        except asyncio.TimeoutError:
            logger.debug("Skipping care push: pipeline busy (%s)", session.user_id)
            return

        try:
            # LLM 生成
            messages = [
                {"role": "system", "content": "你是 Wallace，生成一句简短的关怀语句。"},
                {"role": "user", "content": prompt},
            ]
            text = ""
            async for token in self._llm.chat_stream(messages):
                text += token

            if not text.strip():
                return

            # TTS + 推送
            from wallace.ws.protocol import CareMessage

            await session.ws.send_text(
                CareMessage(content=text.strip(), mood=mood).model_dump_json()
            )
            async for frame in self._tts.synthesize(text.strip()):
                await session.ws.send_bytes(frame)

        finally:
            session.pipeline_lock.release()

    async def _push_all(self, prompt: str, mood: str) -> None:
        """向所有在线 session 推送。"""
        for session in list(self._sessions.values()):
            try:
                await self._push_to_session(session, prompt, mood)
            except Exception:
                logger.exception("Care push failed for %s", session.user_id)

    async def _sedentary_reminder(self) -> None:
        await self._push_all("主人已经坐了很久了，提醒他活动一下", "caring")

    async def _morning_greeting(self) -> None:
        weather = await self._fetch_weather()
        prompt = f"早上好！今天的天气：{weather}。生成一句元气满满的早安问候。"
        await self._push_all(prompt, "happy")

    async def _evening_greeting(self) -> None:
        await self._push_all("夜深了，提醒主人早点休息", "gentle")

    async def _fetch_weather(self) -> str:
        """获取天气信息。失败则返回空字符串。"""
        if not self.weather_config.api_key:
            return "（未配置天气 API）"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    self.weather_config.api_url,
                    params={
                        "key": self.weather_config.api_key,
                        "location": self.weather_config.city,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                now = data["results"][0]["now"]
                return f"{now['text']}，{now['temperature']}°C"
        except Exception as e:
            logger.warning("Weather API failed: %s", e)
            return ""
