"""测试 care/scheduler.py — 定时任务触发、前置检查、冲突处理。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wallace.config import CareConfig, WeatherConfig
from wallace.care.scheduler import CareScheduler


@pytest.fixture
def care_config() -> CareConfig:
    return CareConfig(push_timeout=2)


@pytest.fixture
def weather_config() -> WeatherConfig:
    return WeatherConfig(api_key="test_key")


@pytest.fixture
def care_scheduler(care_config, weather_config, session, mock_llm, mock_tts):
    sessions = {session.user_id: session}
    return CareScheduler(care_config, weather_config, sessions, mock_llm, mock_tts)


class TestPushToSession:
    """单 session 推送。"""

    async def test_push_basic(self, care_scheduler, session, mock_ws):
        await care_scheduler._push_to_session(session, "test prompt", "happy")
        # 应该发送了 care 消息和音频帧
        sent = mock_ws.get_sent_json_messages()
        care_msgs = [m for m in sent if m.get("type") == "care"]
        assert len(care_msgs) == 1
        assert care_msgs[0]["mood"] == "happy"
        assert len(mock_ws.sent_bytes) > 0  # TTS 帧

    async def test_skip_when_user_not_present(self, care_scheduler, session, mock_ws):
        session.proximity_present = False
        await care_scheduler._push_to_session(session, "test", "happy")
        assert len(mock_ws.sent_text) == 0

    async def test_conflict_wait_and_push(self, care_scheduler, session, mock_ws):
        """pipeline_lock 被占 → 等待释放后推送。"""
        async with session.pipeline_lock:
            # 在另一个 task 中推送（会等待 lock）
            task = asyncio.create_task(
                care_scheduler._push_to_session(session, "test", "happy")
            )
            await asyncio.sleep(0.05)
            # task 应该在等待 lock
            assert not task.done()

        # lock 释放后 task 完成
        await asyncio.wait_for(task, timeout=3.0)
        assert len(mock_ws.sent_text) > 0

    async def test_conflict_timeout_discard(self, care_scheduler, session, mock_ws):
        """pipeline_lock 超时 → 丢弃。"""
        care_scheduler.config.push_timeout = 0  # 立即超时
        async with session.pipeline_lock:
            await care_scheduler._push_to_session(session, "test", "happy")
        assert len(mock_ws.sent_text) == 0


class TestPushAll:
    """批量推送。"""

    async def test_push_all_online(self, care_scheduler, mock_ws):
        await care_scheduler._push_all("test", "happy")
        assert len(mock_ws.sent_text) > 0

    async def test_skip_offline(self, care_config, weather_config, mock_llm, mock_tts):
        """无在线 session → 不推送不报错。"""
        scheduler = CareScheduler(care_config, weather_config, {}, mock_llm, mock_tts)
        await scheduler._push_all("test", "happy")  # should not raise


class TestWeatherFetch:
    """天气 API。"""

    async def test_weather_success(self, care_scheduler):

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": [{"now": {"text": "晴", "temperature": "26"}}]
        }

        with patch("wallace.care.scheduler.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_httpx.AsyncClient.return_value = mock_client

            weather = await care_scheduler._fetch_weather()
        assert "晴" in weather
        assert "26" in weather

    async def test_weather_api_failure(self, care_scheduler):
        with patch("wallace.care.scheduler.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("timeout"))
            mock_httpx.AsyncClient.return_value = mock_client

            weather = await care_scheduler._fetch_weather()
        assert weather == ""

    async def test_weather_no_api_key(self, care_scheduler):
        care_scheduler.weather_config.api_key = ""
        weather = await care_scheduler._fetch_weather()
        assert "未配置" in weather


class TestCareJobs:
    """定时任务。"""

    async def test_sedentary_reminder(self, care_scheduler, mock_ws):
        await care_scheduler._sedentary_reminder()
        sent = mock_ws.get_sent_json_messages()
        assert any(m.get("type") == "care" for m in sent)

    async def test_evening_greeting(self, care_scheduler, mock_ws):
        await care_scheduler._evening_greeting()
        sent = mock_ws.get_sent_json_messages()
        assert any(m.get("type") == "care" for m in sent)


class TestBirthdayGreeting:
    """生日祝福测试。"""

    @pytest.mark.xfail(reason="生日祝福功能尚未实现 - 见 architecture.md §care.scheduler 待办")
    async def test_birthday_greeting_on_birthday(self, care_scheduler, session, mock_ws):
        """memory 中 birthday 匹配今天 → 触发生日祝福。

        根据 architecture.md:
        - 特殊日期：生日/纪念日祝福（mood: excited），从 memory 读取
        """
        import datetime

        # 设置用户生日为今天
        today = datetime.date.today().strftime("%m-%d")
        session.memory.important_dates["birthday"] = today

        # 触发生日检查（目前 scheduler 没有此方法，需要实现）
        await care_scheduler._birthday_greeting()

        sent = mock_ws.get_sent_json_messages()
        care_msgs = [m for m in sent if m.get("type") == "care"]
        assert len(care_msgs) >= 1, "生日当天必须发送祝福"
        assert care_msgs[0]["mood"] == "excited", "生日祝福 mood 应为 excited"

    @pytest.mark.xfail(reason="生日祝福功能尚未实现")
    async def test_no_birthday_greeting_on_other_days(self, care_scheduler, session, mock_ws):
        """非生日当天不触发祝福。"""
        # 设置生日为非今天的日期
        session.memory.important_dates["birthday"] = "01-01"  # 假设不是今天

        await care_scheduler._birthday_greeting()

        sent = mock_ws.get_sent_json_messages()
        care_msgs = [m for m in sent if m.get("type") == "care"]
        # 非生日不应推送生日祝福
        assert len(care_msgs) == 0 or "生日" not in care_msgs[0].get("content", "")
