"""传感器数据处理 — 缓存、LLM 上下文生成、阈值告警。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wallace.config import SensorConfig
    from wallace.ws.session import Session


class SensorProcessor:
    """处理传感器数据上报。"""

    def __init__(self, config: SensorConfig) -> None:
        self.config = config
        self._last_alert_time: dict[str, float] = {}

    def update_cache(self, session: Session, data: dict) -> None:
        """更新 session 中的传感器缓存。"""
        cache = session.sensor_cache
        cache.temp = data.get("temp", cache.temp)
        cache.humidity = data.get("humidity", cache.humidity)
        cache.light = data.get("light", cache.light)
        cache.air_quality = data.get("air_quality", cache.air_quality)
        cache.updated_at = time.monotonic()

    def update_proximity(self, session: Session, data: dict) -> None:
        """更新 proximity 状态。"""
        session.proximity_present = data.get("user_present", session.proximity_present)

    def build_llm_context(self, session: Session) -> str:
        """将传感器数据格式化为 LLM 上下文字符串。"""
        cache = session.sensor_cache
        if cache.updated_at == 0.0:
            return ""

        parts = []
        parts.append(f"室温{cache.temp:.0f}°C")
        parts.append(f"湿度{cache.humidity:.0f}%")

        if cache.light < self.config.light_dark_threshold:
            parts.append("光线较暗")
        elif cache.light > 500:
            parts.append("光线明亮")
        else:
            parts.append(f"光线{cache.light:.0f}lux")

        if cache.air_quality > self.config.air_quality_threshold:
            parts.append("空气质量较差")
        else:
            parts.append("空气质量良好")

        return "当前环境：" + "，".join(parts)

    def check_alerts(self, session: Session) -> list[tuple[str, str]]:
        """检查阈值并返回需要触发的告警列表 [(alert_type, suggestion)]。

        内含防抖逻辑。
        """
        alerts: list[tuple[str, str]] = []
        cache = session.sensor_cache
        now = time.monotonic()

        checks = [
            (
                "air_quality_bad",
                cache.air_quality > self.config.air_quality_threshold,
                "空气质量不太好，建议开窗通通风",
            ),
            (
                "light_too_dark",
                cache.light < self.config.light_dark_threshold,
                "光线有点暗，要不要开个灯",
            ),
            (
                "temp_too_high",
                cache.temp > self.config.temp_high,
                f"温度有点高({cache.temp:.0f}°C)，注意降温",
            ),
            (
                "temp_too_low",
                cache.temp < self.config.temp_low,
                f"温度有点低({cache.temp:.0f}°C)，注意保暖",
            ),
        ]

        for alert_type, triggered, suggestion in checks:
            if not triggered:
                continue
            last_time = self._last_alert_time.get(alert_type)
            if last_time is not None and now - last_time < self.config.alert_cooldown:
                continue
            self._last_alert_time[alert_type] = now
            alerts.append((alert_type, suggestion))

        return alerts
