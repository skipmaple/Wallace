"""情绪解析 — 从 LLM 回复中提取 [mood:xxx] 标签。"""

from __future__ import annotations

import re
from enum import Enum

_MOOD_PATTERN = re.compile(r"\[mood:(\w+)\]")


class Mood(str, Enum):
    HAPPY = "happy"
    SAD = "sad"
    THINKING = "thinking"
    ANGRY = "angry"
    SLEEPY = "sleepy"
    SURPRISED = "surprised"
    TSUNDERE = "tsundere"
    NEUTRAL = "neutral"


_VALID_MOODS = {m.value for m in Mood}


def extract_mood(text: str) -> tuple[Mood, str]:
    """从文本中提取情绪标签并返回 (mood, 清洗后文本)。

    取最后一个 [mood:xxx] 标签。未匹配或非法值返回 NEUTRAL。
    """
    matches = list(_MOOD_PATTERN.finditer(text))
    if not matches:
        return Mood.NEUTRAL, text

    last = matches[-1]
    mood_str = last.group(1)
    cleaned = _MOOD_PATTERN.sub("", text).strip()

    if mood_str in _VALID_MOODS:
        return Mood(mood_str), cleaned
    return Mood.NEUTRAL, cleaned
