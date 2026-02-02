"""测试 emotion.py — 情绪提取。"""

from __future__ import annotations

import pytest

from wallace.emotion import Mood, extract_mood


class TestExtractMood:
    """情绪标签提取。"""

    @pytest.mark.parametrize(
        "mood_str",
        ["happy", "sad", "thinking", "angry", "sleepy", "surprised", "tsundere", "neutral"],
    )
    def test_all_valid_moods(self, mood_str):
        text = f"你好[mood:{mood_str}]"
        mood, cleaned = extract_mood(text)
        assert mood == Mood(mood_str)
        assert cleaned == "你好"

    def test_no_mood_tag(self):
        mood, cleaned = extract_mood("你好呀")
        assert mood == Mood.NEUTRAL
        assert cleaned == "你好呀"

    def test_mood_at_end(self):
        mood, cleaned = extract_mood("今天心情不错[mood:happy]")
        assert mood == Mood.HAPPY
        assert cleaned == "今天心情不错"

    def test_mood_at_start(self):
        mood, cleaned = extract_mood("[mood:sad]我有点难过")
        assert mood == Mood.SAD
        assert cleaned == "我有点难过"

    def test_mood_in_middle(self):
        mood, cleaned = extract_mood("你好[mood:angry]世界")
        assert mood == Mood.ANGRY
        assert "你好" in cleaned
        assert "世界" in cleaned

    def test_multiple_moods_takes_last(self):
        mood, cleaned = extract_mood("[mood:sad]开头[mood:happy]结尾")
        assert mood == Mood.HAPPY
        assert "开头" in cleaned
        assert "结尾" in cleaned

    def test_invalid_mood_value(self):
        mood, cleaned = extract_mood("你好[mood:unknown_value]")
        assert mood == Mood.NEUTRAL
        assert cleaned == "你好"

    def test_text_cleaning_removes_all_tags(self):
        mood, cleaned = extract_mood("[mood:sad]中间[mood:happy]")
        assert "[mood:" not in cleaned

    def test_empty_text(self):
        mood, cleaned = extract_mood("")
        assert mood == Mood.NEUTRAL
        assert cleaned == ""

    def test_only_tag(self):
        mood, cleaned = extract_mood("[mood:happy]")
        assert mood == Mood.HAPPY
        assert cleaned == ""

    def test_tag_with_space_inside_not_matched(self):
        """[mood: happy] 带空格不匹配（\w+ 不含空格）。"""
        mood, cleaned = extract_mood("你好[mood: happy]")
        assert mood == Mood.NEUTRAL
