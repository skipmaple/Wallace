"""用户记忆持久化 — JSON 文件存储。"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from wallace.ws.session import UserMemory

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "memory"


class MemoryStore:
    """管理单个用户的记忆持久化。"""

    def __init__(
        self, user_id: str, data_dir: Path = _DEFAULT_DATA_DIR, sync_interval: int = 300
    ) -> None:
        self.user_id = user_id
        self.data_dir = data_dir
        self.sync_interval = sync_interval
        self._file = data_dir / f"{user_id}.json"
        self._last_sync: float = 0.0
        self._last_snapshot: dict[str, Any] = {}

    def load(self) -> UserMemory:
        """从 JSON 文件加载记忆。文件不存在或损坏则返回默认空记忆。"""
        if not self._file.exists():
            return UserMemory()
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            mem = UserMemory.from_dict(data)
            self._last_snapshot = mem.to_dict()
            return mem
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to load memory for %s: %s, using defaults", self.user_id, e)
            return UserMemory()

    def save(self, memory: UserMemory) -> None:
        """保存记忆到 JSON 文件（原子写入：临时文件 + rename）。"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = memory.to_dict()
        # 原子写入
        fd, tmp_path = tempfile.mkstemp(dir=self.data_dir, suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Path(tmp_path).replace(self._file)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def has_changes(self, memory: UserMemory) -> bool:
        """检查记忆是否有变更。"""
        return memory.to_dict() != self._last_snapshot

    def should_sync(self) -> bool:
        """检查是否到了同步时间（节流：最多每 sync_interval 秒一次）。"""
        return time.monotonic() - self._last_sync >= self.sync_interval

    def mark_synced(self, memory: UserMemory) -> None:
        """标记已同步。"""
        self._last_sync = time.monotonic()
        self._last_snapshot = memory.to_dict()
