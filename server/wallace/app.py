"""FastAPI 应用工厂 + lifespan。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from wallace.config import Settings, load_settings
from wallace.pipeline.asr import ASREngine
from wallace.pipeline.llm import LLMClient
from wallace.pipeline.tts import TTSManager
from wallace.pipeline.orchestrator import Orchestrator
from wallace.sensor import SensorProcessor
from wallace.wakeword import WakewordVerifier
from wallace.smarthome.mqtt import MQTTManager
from wallace.care.scheduler import CareScheduler
from wallace.ws.handler import WebSocketHandler
from wallace.ws.session import Session

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭生命周期管理。"""
    settings: Settings = app.state.settings

    # 1. 日志
    logging.basicConfig(
        level=getattr(logging, settings.server.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # 2. ASR
    asr = ASREngine(settings.asr)
    await asr.load_model()

    # 3. LLM
    llm = LLMClient(settings.llm)
    await llm.start()

    # 4. TTS
    tts = TTSManager(settings.tts)

    # 5. MQTT
    mqtt = MQTTManager(settings.mqtt)
    await mqtt.connect()

    # 6. Sensor
    sensor = SensorProcessor(settings.sensor)

    # 7. Wakeword
    wakeword = WakewordVerifier()

    # 8. Sessions
    sessions: dict[str, Session] = {}

    # 9. Orchestrator
    orchestrator = Orchestrator(asr, llm, tts, sensor)

    # 10. Care scheduler
    care = CareScheduler(settings.care, settings.weather, sessions, llm, tts)
    await care.start()

    # 11. Handler
    handler = WebSocketHandler(sessions, orchestrator, sensor, wakeword, mqtt)

    # Store on app state
    app.state.handler = handler
    app.state.sessions = sessions
    app.state.llm = llm
    app.state.mqtt = mqtt
    app.state.care = care

    yield

    # Shutdown (reverse order)
    await care.stop()
    for session in list(sessions.values()):
        await orchestrator.cancel_pipeline(session)
    await mqtt.disconnect()
    await llm.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    """创建 FastAPI 应用。"""
    if settings is None:
        settings = load_settings()

    app = FastAPI(title="Wallace Server", lifespan=lifespan)
    app.state.settings = settings

    @app.websocket("/ws/{user_id}")
    async def ws_endpoint(ws: WebSocket, user_id: str):
        handler: WebSocketHandler = app.state.handler
        await handler.handle_connection(ws, user_id)

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "llm": app.state.llm.is_healthy if hasattr(app.state, "llm") else False,
            "mqtt": app.state.mqtt.is_connected if hasattr(app.state, "mqtt") else False,
        }

    return app
