"""测试 llm.py — LLM 对话、system prompt 组装、情绪解析、人格切换。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wallace.config import LLMConfig
from wallace.pipeline.llm import LLMClient, _PERSONALITY_PROMPTS


@pytest.fixture
def llm_config() -> LLMConfig:
    return LLMConfig(max_history_turns=3, max_tokens=64)


@pytest.fixture
def llm_client(llm_config) -> LLMClient:
    return LLMClient(llm_config)


class TestSystemPrompt:
    """system prompt 组装。"""

    def test_contains_personality(self, llm_client, session):
        messages = llm_client.build_messages(session, "你好")
        system = messages[0]["content"]
        assert "Wallace" in system

    def test_contains_memory(self, llm_client, session):
        messages = llm_client.build_messages(session, "你好")
        system = messages[0]["content"]
        assert "小明" in system
        assert "编程" in system

    def test_contains_sensor_context(self, llm_client, session):
        messages = llm_client.build_messages(session, "你好", "当前环境：室温26°C")
        system = messages[0]["content"]
        assert "室温26°C" in system

    def test_contains_mood_instruction(self, llm_client, session):
        messages = llm_client.build_messages(session, "你好")
        system = messages[0]["content"]
        assert "[mood:" in system

    def test_user_message_at_end(self, llm_client, session):
        messages = llm_client.build_messages(session, "今天天气怎么样")
        assert messages[-1] == {"role": "user", "content": "今天天气怎么样"}


class TestHistoryWindow:
    """对话历史窗口。"""

    def test_history_truncation(self, llm_client, session):
        # max_history_turns = 3, so 6 messages max
        for i in range(10):
            session.chat_history.append({"role": "user", "content": f"msg{i}"})
            session.chat_history.append({"role": "assistant", "content": f"resp{i}"})

        messages = llm_client.build_messages(session, "new")
        # system + last 6 history + user = 8
        history_msgs = [m for m in messages if m["role"] != "system" and m != messages[-1]]
        assert len(history_msgs) == 6  # 3 turns × 2

    def test_empty_history(self, llm_client, session):
        session.chat_history.clear()
        messages = llm_client.build_messages(session, "hello")
        # system + user = 2
        assert len(messages) == 2


class TestPersonalitySwitch:
    """人格切换。"""

    def test_switch_clears_history(self, llm_client, session):
        session.chat_history.append({"role": "user", "content": "test"})
        llm_client.switch_personality(session, "tsundere")
        assert session.personality == "tsundere"
        assert session.chat_history == []

    def test_all_personalities_have_prompts(self):
        for p in ["normal", "cool", "talkative", "tsundere"]:
            assert p in _PERSONALITY_PROMPTS


class TestHealthCheck:
    """LLM 健康检查。"""

    async def test_healthy(self, llm_client):
        llm_client._client = AsyncMock()
        llm_client._client.get = AsyncMock(
            return_value=MagicMock(status_code=200)
        )
        result = await llm_client.health_check()
        assert result is True
        assert llm_client.is_healthy is True

    async def test_unhealthy_500(self, llm_client):
        llm_client._client = AsyncMock()
        llm_client._client.get = AsyncMock(
            return_value=MagicMock(status_code=500)
        )
        result = await llm_client.health_check()
        assert result is False
        assert llm_client.is_healthy is False

    async def test_unhealthy_timeout(self, llm_client):
        import httpx

        llm_client._client = AsyncMock()
        llm_client._client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        result = await llm_client.health_check()
        assert result is False

    async def test_no_client(self, llm_client):
        """客户端未初始化。"""
        assert await llm_client.health_check() is False


class TestTreehouseMode:
    """树洞模式。"""

    def test_treehouse_flag(self, session):
        session.treehouse_mode = True
        assert session.treehouse_mode is True


class TestStreamParsing:
    """Ollama 流式 JSON lines 解析。"""

    async def test_stream_tokens(self, llm_client):
        """正常流式响应应逐 token 产出。"""
        # Mock Ollama 返回的流式 JSON lines
        stream_lines = [
            '{"message":{"content":"你"},"done":false}',
            '{"message":{"content":"好"},"done":false}',
            '{"message":{"content":"！"},"done":false}',
            '{"message":{"content":""},"done":true}',
        ]

        class MockAsyncIterator:
            def __init__(self, lines):
                self._lines = iter(lines)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self._lines)
                except StopIteration:
                    raise StopAsyncIteration

        class MockResponse:
            def raise_for_status(self):
                pass

            def aiter_lines(self):
                return MockAsyncIterator(stream_lines)

        # 创建 async context manager mock
        import contextlib

        @contextlib.asynccontextmanager
        async def mock_stream(method, url, json):
            yield MockResponse()

        llm_client._client = AsyncMock()
        llm_client._client.stream = mock_stream

        tokens = []
        async for token in llm_client.chat_stream([{"role": "user", "content": "hi"}]):
            tokens.append(token)

        assert tokens == ["你", "好", "！"]

    async def test_stream_empty_lines_skipped(self, llm_client):
        """空行应被跳过。"""
        stream_lines = [
            '{"message":{"content":"test"},"done":false}',
            "",  # 空行
            "   ",  # 空白行
            '{"message":{"content":""},"done":true}',
        ]

        class MockAsyncIterator:
            def __init__(self, lines):
                self._lines = iter(lines)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self._lines)
                except StopIteration:
                    raise StopAsyncIteration

        class MockResponse:
            def raise_for_status(self):
                pass

            def aiter_lines(self):
                return MockAsyncIterator(stream_lines)

        import contextlib

        @contextlib.asynccontextmanager
        async def mock_stream(method, url, json):
            yield MockResponse()

        llm_client._client = AsyncMock()
        llm_client._client.stream = mock_stream

        tokens = []
        async for token in llm_client.chat_stream([{"role": "user", "content": "hi"}]):
            tokens.append(token)

        assert tokens == ["test"]

    async def test_stream_stops_on_done(self, llm_client):
        """收到 done:true 应停止。"""
        stream_lines = [
            '{"message":{"content":"first"},"done":false}',
            '{"message":{"content":""},"done":true}',
            '{"message":{"content":"should_not_yield"},"done":false}',
        ]

        class MockAsyncIterator:
            def __init__(self, lines):
                self._lines = iter(lines)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self._lines)
                except StopIteration:
                    raise StopAsyncIteration

        class MockResponse:
            def raise_for_status(self):
                pass

            def aiter_lines(self):
                return MockAsyncIterator(stream_lines)

        import contextlib

        @contextlib.asynccontextmanager
        async def mock_stream(method, url, json):
            yield MockResponse()

        llm_client._client = AsyncMock()
        llm_client._client.stream = mock_stream

        tokens = []
        async for token in llm_client.chat_stream([{"role": "user", "content": "hi"}]):
            tokens.append(token)

        assert tokens == ["first"]
        assert "should_not_yield" not in tokens

    async def test_stream_no_client_raises(self, llm_client):
        """客户端未初始化应抛异常。"""
        llm_client._client = None
        with pytest.raises(RuntimeError, match="not started"):
            async for _ in llm_client.chat_stream([{"role": "user", "content": "hi"}]):
                pass


class TestPersonalityPrompts:
    """不同人格 prompt 验证。"""

    @pytest.mark.parametrize("personality,expected_keyword", [
        ("normal", "温暖"),
        ("cool", "高冷"),
        ("talkative", "话痨"),
        ("tsundere", "傲娇"),
    ])
    def test_personality_prompts_unique(self, llm_client, session, personality, expected_keyword):
        """各人格应有独特的 system prompt。"""
        session.personality = personality
        messages = llm_client.build_messages(session, "你好")
        system_prompt = messages[0]["content"]

        # 验证关键词存在
        assert expected_keyword in system_prompt, \
            f"Personality '{personality}' should contain '{expected_keyword}'"

    def test_tsundere_has_speech_pattern(self, llm_client, session):
        """傲娇人格应有特定口癖描述。"""
        session.personality = "tsundere"
        messages = llm_client.build_messages(session, "你好")
        system_prompt = messages[0]["content"]

        # 傲娇口癖
        assert "才不是" in system_prompt or "哼" in system_prompt

    def test_unknown_personality_fallback(self, llm_client, session):
        """未知人格应使用默认 normal。"""
        session.personality = "unknown_personality"
        messages = llm_client.build_messages(session, "你好")
        system_prompt = messages[0]["content"]

        # 应使用 normal 的 prompt
        assert "温暖" in system_prompt
