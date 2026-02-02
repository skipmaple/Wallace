"""图片分析 — OV7670 抓拍 → LLM 多模态（可选）。"""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


async def analyze_image(image_base64: str, llm_base_url: str) -> str:
    """将 base64 图片送入 LLM 多模态分析。"""
    # TODO: Implement when multimodal LLM is available
    logger.info("Image analysis requested (not implemented)")
    return ""
