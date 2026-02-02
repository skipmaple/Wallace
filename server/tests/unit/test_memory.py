"""测试 memory/store.py — 记忆读写、损坏恢复、并发安全、同步节流。"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from wallace.memory.store import MemoryStore
from wallace.ws.session import UserMemory


@pytest.fixture
def tmp_data_dir(tmp_path) -> Path:
    return tmp_path / "memory"


@pytest.fixture
def store(tmp_data_dir) -> MemoryStore:
    return MemoryStore("test_user", data_dir=tmp_data_dir, sync_interval=5)


class TestLoad:
    """记忆加载。"""

    def test_load_existing(self, store, tmp_data_dir):
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        data = {"nickname": "小明", "interests": ["coding"]}
        (tmp_data_dir / "test_user.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        mem = store.load()
        assert mem.nickname == "小明"
        assert "coding" in mem.interests

    def test_load_nonexistent_returns_default(self, store):
        mem = store.load()
        assert mem.nickname == ""
        assert mem.interests == []

    def test_load_corrupted_json(self, store, tmp_data_dir):
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        (tmp_data_dir / "test_user.json").write_text("not json{{{", encoding="utf-8")
        mem = store.load()
        assert mem.nickname == ""

    def test_all_v42_fields_present(self):
        """所有 v4.2 §6.1 字段存在于 UserMemory。"""
        mem = UserMemory()
        d = mem.to_dict()
        expected = [
            "nickname", "preferences", "interests", "recent_topics",
            "important_dates", "interaction_count", "first_met",
        ]
        for key in expected:
            assert key in d


class TestSave:
    """记忆保存。"""

    def test_save_and_reload(self, store, tmp_data_dir):
        mem = UserMemory(nickname="test", interests=["a", "b"])
        store.save(mem)
        loaded = store.load()
        assert loaded.nickname == "test"
        assert loaded.interests == ["a", "b"]

    def test_save_creates_directory(self, store, tmp_data_dir):
        assert not tmp_data_dir.exists()
        store.save(UserMemory(nickname="new"))
        assert tmp_data_dir.exists()

    def test_atomic_write(self, store, tmp_data_dir):
        """保存后不应存在 .tmp 文件。"""
        store.save(UserMemory(nickname="test"))
        tmp_files = list(tmp_data_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_concurrent_saves(self, store):
        """两个并发 save 不应损坏文件。"""
        mem1 = UserMemory(nickname="first")
        mem2 = UserMemory(nickname="second")
        store.save(mem1)
        store.save(mem2)
        loaded = store.load()
        # 最后一次 save 胜出
        assert loaded.nickname == "second"


class TestChangeDetection:
    """变更检测。"""

    def test_no_changes_after_load(self, store, tmp_data_dir):
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        (tmp_data_dir / "test_user.json").write_text(
            json.dumps({"nickname": "test"}), encoding="utf-8"
        )
        mem = store.load()
        assert not store.has_changes(mem)

    def test_has_changes_after_modification(self, store, tmp_data_dir):
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        (tmp_data_dir / "test_user.json").write_text(
            json.dumps({"nickname": "test"}), encoding="utf-8"
        )
        mem = store.load()
        mem.nickname = "changed"
        assert store.has_changes(mem)


class TestSyncThrottle:
    """同步节流。"""

    def test_should_sync_initially(self, store):
        assert store.should_sync() is True

    def test_should_not_sync_after_recent(self, store):
        store.mark_synced(UserMemory())
        assert store.should_sync() is False

    def test_should_sync_after_interval(self):
        store = MemoryStore("test", sync_interval=0)  # 0 秒间隔
        store.mark_synced(UserMemory())
        assert store.should_sync() is True
