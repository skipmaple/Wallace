"""流水线编排 — ASR → LLM → TTS 串联。"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from wallace.emotion import extract_mood
from wallace.ws.protocol import (
    TTSCancelMessage,
    TTSEndMessage,
    TTSStartMessage,
    TextMessage,
)
from wallace.ws.session import PipelineState

if TYPE_CHECKING:
    from wallace.pipeline.asr import ASREngine
    from wallace.pipeline.llm import LLMClient
    from wallace.pipeline.tts import TTSManager
    from wallace.sensor import SensorProcessor
    from wallace.ws.session import Session

logger = logging.getLogger(__name__)

# 分句标点
_SENTENCE_ENDINGS = set("。！？；\n")


class Orchestrator:
    """ASR → LLM → TTS 流水线编排器。"""

    def __init__(
        self,
        asr: ASREngine,
        llm: LLMClient,
        tts: TTSManager,
        sensor: SensorProcessor,
    ) -> None:
        self.asr = asr
        self.llm = llm
        self.tts = tts
        self.sensor = sensor

    async def handle_audio_start(self, session: Session) -> None:
        """处理 audio_start：打断 + 开始录音。"""
        await self.cancel_pipeline(session)
        session.clear_audio()
        session.transition_to(PipelineState.RECORDING)

    async def handle_audio_end(self, session: Session) -> None:
        """处理 audio_end：启动流水线。"""
        session.transition_to(PipelineState.PROCESSING)
        task = asyncio.create_task(self._run_pipeline(session))
        session.pipeline_task = task

    async def cancel_pipeline(self, session: Session) -> None:
        """取消当前流水线并通知 ESP32。"""
        # 先保存状态，因为 await 后任务的 except 处理可能改变状态
        was_speaking = session.state == PipelineState.SPEAKING

        if session.pipeline_task and not session.pipeline_task.done():
            session.pipeline_task.cancel()
            try:
                await session.pipeline_task
            except asyncio.CancelledError:
                pass

        # 如果取消前正在说话，发送 tts_cancel 通知 ESP32 停止播放
        if was_speaking:
            await session.ws.send_text(TTSCancelMessage().model_dump_json())

        session.state = PipelineState.IDLE
        session.pipeline_task = None

    async def _run_pipeline(self, session: Session) -> None:
        """完整流水线：ASR → LLM → TTS。"""
        try:
            # 1. ASR
            audio = session.get_audio_array()
            session.clear_audio()

            if not self.asr.vad_has_speech(audio):
                session.transition_to(PipelineState.IDLE)
                return

            text = await self.asr.transcribe(audio)
            if not text:
                session.transition_to(PipelineState.IDLE)
                return

            # 树洞模式：只做 ASR
            if session.treehouse_mode:
                logger.info("[treehouse] ASR: %s", text)
                session.transition_to(PipelineState.IDLE)
                return

            # 2. 组装 LLM 消息
            sensor_ctx = self.sensor.build_llm_context(session)
            messages = self.llm.build_messages(session, text, sensor_ctx)

            # 3. LLM 流式生成 + 4. 分句 TTS
            full_response = ""
            sentence_buffer = ""
            first_sentence = True

            session.transition_to(PipelineState.SPEAKING)

            async for token in self.llm.chat_stream(messages):
                full_response += token
                sentence_buffer += token

                # 检查是否有完整句子
                for i, ch in enumerate(sentence_buffer):
                    if ch in _SENTENCE_ENDINGS:
                        sentence = sentence_buffer[: i + 1].strip()
                        sentence_buffer = sentence_buffer[i + 1 :]

                        if sentence:
                            if first_sentence:
                                await session.ws.send_text(
                                    TTSStartMessage(mood="thinking").model_dump_json()
                                )
                                first_sentence = True  # will be set to False below
                                first_sentence = False

                            async for frame in self.tts.synthesize(sentence):
                                await session.ws.send_bytes(frame)
                        break

            # 处理剩余 buffer（无标点结尾的情况）
            remaining = sentence_buffer.strip()
            if remaining:
                # 去掉 mood 标签
                _, cleaned = extract_mood(remaining)
                if cleaned:
                    if first_sentence:
                        await session.ws.send_text(
                            TTSStartMessage(mood="thinking").model_dump_json()
                        )
                        first_sentence = False
                    async for frame in self.tts.synthesize(cleaned):
                        await session.ws.send_bytes(frame)

            # 5. 情绪提取
            mood, cleaned_full = extract_mood(full_response)

            # 发送最终文本 + mood
            await session.ws.send_text(
                TextMessage(content=cleaned_full, partial=False, mood=mood.value).model_dump_json()
            )

            # 6. tts_end
            if not first_sentence:  # 至少发送过一句 TTS
                await session.ws.send_text(TTSEndMessage().model_dump_json())

            # 7. 更新对话历史
            session.chat_history.append({"role": "user", "content": text})
            session.chat_history.append({"role": "assistant", "content": cleaned_full})

            session.state = PipelineState.IDLE

        except asyncio.CancelledError:
            logger.info("Pipeline cancelled for session %s", session.user_id)
            session.state = PipelineState.IDLE
            raise
        except Exception:
            logger.exception("Pipeline error for session %s", session.user_id)
            session.state = PipelineState.IDLE

    async def push_random_fact(self, session: Session) -> None:
        """摇一摇触发：生成随机冷知识并通过 TTS 推送。

        流程：
        1. 检查状态是否空闲（忙碌中则忽略）
        2. 构建冷知识 prompt
        3. 调用 LLM 流式生成
        4. 分句 TTS 合成
        5. 发送 tts_start → PCM帧 → text → tts_end
        """
        async with session.pipeline_lock:
            if session.state != PipelineState.IDLE:
                logger.debug("Ignoring shake: session %s not idle", session.user_id)
                return

            # 直接设置状态（跳过 RECORDING，这是主动推送场景）
            session.state = PipelineState.PROCESSING

            try:
                # 构建冷知识 prompt（不加入对话历史）
                fact_prompt = (
                    "请用一句话分享一个随机的有趣冷知识，"
                    "要有趣、简短，结尾加上 [mood:surprised]。"
                )
                messages = [{"role": "user", "content": fact_prompt}]

                # LLM 流式生成
                full_response = ""
                sentence_buffer = ""
                first_sentence = True

                session.state = PipelineState.SPEAKING

                async for token in self.llm.chat_stream(messages):
                    full_response += token
                    sentence_buffer += token

                    # 检查是否有完整句子
                    for i, ch in enumerate(sentence_buffer):
                        if ch in _SENTENCE_ENDINGS:
                            sentence = sentence_buffer[: i + 1].strip()
                            sentence_buffer = sentence_buffer[i + 1 :]

                            if sentence:
                                if first_sentence:
                                    await session.ws.send_text(
                                        TTSStartMessage(mood="surprised").model_dump_json()
                                    )
                                    first_sentence = False

                                async for frame in self.tts.synthesize(sentence):
                                    await session.ws.send_bytes(frame)
                            break

                # 处理剩余 buffer
                remaining = sentence_buffer.strip()
                if remaining:
                    _, cleaned = extract_mood(remaining)
                    if cleaned:
                        if first_sentence:
                            await session.ws.send_text(
                                TTSStartMessage(mood="surprised").model_dump_json()
                            )
                            first_sentence = False
                        async for frame in self.tts.synthesize(cleaned):
                            await session.ws.send_bytes(frame)

                # 情绪提取
                mood, cleaned_full = extract_mood(full_response)

                # 发送最终文本 + mood
                await session.ws.send_text(
                    TextMessage(
                        content=cleaned_full, partial=False, mood=mood.value
                    ).model_dump_json()
                )

                # tts_end
                if not first_sentence:
                    await session.ws.send_text(TTSEndMessage().model_dump_json())

                session.state = PipelineState.IDLE
                logger.info("Random fact pushed to session %s", session.user_id)

            except asyncio.CancelledError:
                logger.info("Random fact cancelled for session %s", session.user_id)
                session.state = PipelineState.IDLE
                raise
            except Exception:
                logger.exception("Random fact error for session %s", session.user_id)
                session.state = PipelineState.IDLE
