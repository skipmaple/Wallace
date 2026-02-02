"""配置管理 — Pydantic Settings 从 TOML 加载。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings

_DEFAULT_TOML = Path(__file__).resolve().parent.parent / "config" / "default.toml"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class ASRConfig(BaseModel):
    model: str = "large-v3-turbo"
    device: Literal["cuda", "cpu"] = "cuda"
    compute_type: Literal["float16", "int8", "float32"] = "float16"
    language: str = "zh"
    vad_threshold: float = 0.5


class LLMConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "deepseek-r1:8b"
    temperature: float = 0.7
    max_tokens: int = 512
    max_history_turns: int = 10
    health_check_interval: int = 60


class TTSConfig(BaseModel):
    default_backend: Literal["edge", "cosyvoice"] = "edge"
    edge_voice: str = "zh-CN-XiaoxiaoNeural"
    cosyvoice_url: str = "http://localhost:9880"
    cosyvoice_voice: str = "default"


class MQTTConfig(BaseModel):
    broker: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""
    topic_prefix: str = "wallace/home"
    reconnect_interval: int = 5


class CareConfig(BaseModel):
    sedentary_interval_hours: int = 2
    morning_time: str = "07:30"
    evening_time: str = "22:00"
    push_timeout: int = 30


class SensorConfig(BaseModel):
    report_interval: int = 10
    alert_cooldown: int = 300
    air_quality_threshold: int = 200
    light_dark_threshold: int = 50
    temp_high: int = 35
    temp_low: int = 10
    proximity_default_present: bool = True


class WeatherConfig(BaseModel):
    api_url: str = "https://api.seniverse.com/v3/weather/now.json"
    api_key: str = ""
    city: str = "beijing"


class Settings(BaseSettings):
    server: ServerConfig = ServerConfig()
    asr: ASRConfig = ASRConfig()
    llm: LLMConfig = LLMConfig()
    tts: TTSConfig = TTSConfig()
    mqtt: MQTTConfig = MQTTConfig()
    care: CareConfig = CareConfig()
    sensor: SensorConfig = SensorConfig()
    weather: WeatherConfig = WeatherConfig()

    model_config = {"env_prefix": "WALLACE_", "env_nested_delimiter": "__"}


def load_settings(toml_path: Path = _DEFAULT_TOML) -> Settings:
    """从 TOML 文件加载配置，环境变量可覆盖。"""
    import sys

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    if toml_path.exists():
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        return Settings(**data)
    return Settings()
