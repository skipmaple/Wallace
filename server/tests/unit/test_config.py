"""测试 config.py — 配置加载、环境变量覆盖、验证。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from wallace.config import Settings, load_settings

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadSettings:
    """TOML 文件加载。"""

    def test_load_default_toml(self):
        settings = load_settings(FIXTURES / "test_config.toml")
        assert settings.server.host == "127.0.0.1"
        assert settings.server.port == 8999
        assert settings.asr.model == "tiny"
        assert settings.asr.device == "cpu"
        assert settings.llm.model == "deepseek-r1:8b"
        assert settings.tts.default_backend == "edge"
        assert settings.mqtt.topic_prefix == "wallace/test"
        assert settings.sensor.alert_cooldown == 10
        assert settings.weather.api_key == "test_key"

    def test_load_nonexistent_file_uses_defaults(self):
        settings = load_settings(Path("/nonexistent/path.toml"))
        assert settings.server.host == "0.0.0.0"
        assert settings.server.port == 8000
        assert settings.asr.model == "large-v3-turbo"

    def test_test_config_toml_loads_successfully(self):
        settings = load_settings(FIXTURES / "test_config.toml")
        assert settings.server.log_level == "DEBUG"
        assert settings.llm.max_tokens == 64
        assert settings.care.push_timeout == 5


class TestEnvironmentOverride:
    """环境变量覆盖。"""

    def test_env_override_llm_model(self, monkeypatch):
        monkeypatch.setenv("WALLACE_LLM__MODEL", "llama3:8b")
        settings = Settings()
        assert settings.llm.model == "llama3:8b"

    def test_env_override_server_port(self, monkeypatch):
        monkeypatch.setenv("WALLACE_SERVER__PORT", "9999")
        settings = Settings()
        assert settings.server.port == 9999


class TestValidation:
    """配置验证。"""

    def test_invalid_device_value(self):
        with pytest.raises(ValidationError):
            Settings(asr={"device": "tpu"})

    def test_invalid_log_level(self):
        with pytest.raises(ValidationError):
            Settings(server={"log_level": "TRACE"})

    def test_invalid_tts_backend(self):
        with pytest.raises(ValidationError):
            Settings(tts={"default_backend": "unknown"})

    def test_all_fields_have_defaults(self):
        """所有字段都有默认值，空构造不报错。"""
        settings = Settings()
        assert settings.server.host is not None
        assert settings.asr.vad_threshold > 0
        assert settings.sensor.alert_cooldown > 0
