# Wallace PC Server

Wallace 桌面 AI 机器人的 PC 服务端，负责语音识别 (ASR)、大语言模型对话 (LLM)、语音合成 (TTS) 等 AI 处理流程。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ESP32-S3 (N32R16V)                          │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐           │
│  │ INMP441   │ │ MAX98357A │ │ GC9A01    │ │ 传感器组   │           │
│  │ 麦克风    │ │ 功放      │ │ 圆形屏幕  │ │ I2C/ADC   │           │
│  └─────┬─────┘ └─────▲─────┘ └───────────┘ └─────┬─────┘           │
│        │             │                           │                  │
│        │  PCM 音频   │   PCM 音频 + 情绪标签     │ 传感器数据       │
└────────┼─────────────┼───────────────────────────┼──────────────────┘
         │             │                           │
         │         WebSocket                       │
         ▼             │                           ▼
┌────────────────────────────────────────────────────────────────────┐
│                        PC Server (本项目)                           │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                      WebSocket Handler                      │    │
│  │                     /ws/{user_id}                          │    │
│  └────────────────────────────┬───────────────────────────────┘    │
│                               │                                     │
│  ┌────────────────────────────▼───────────────────────────────┐    │
│  │                      Pipeline 流水线                        │    │
│  │                                                            │    │
│  │  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐        │    │
│  │  │  ASR   │──▶│ Memory │──▶│  LLM   │──▶│  TTS   │        │    │
│  │  │Whisper │   │ 记忆注入│   │ Ollama │   │Edge/CV │        │    │
│  │  └────────┘   └────────┘   └────────┘   └────────┘        │    │
│  │                               │                            │    │
│  │                        [mood:xxx] 情绪提取                  │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │
│  │ Care 关怀    │ │ Sensor 传感  │ │ MQTT 智能家居│                │
│  │ 久坐/早晚安  │ │ 阈值告警     │ │ 场景联动     │                │
│  └──────────────┘ └──────────────┘ └──────────────┘                │
└────────────────────────────────────────────────────────────────────┘
```

## 核心模块

| 模块 | 路径 | 功能 |
|------|------|------|
| **WebSocket** | `wallace/ws/` | 协议定义、会话管理、消息路由 |
| **ASR** | `wallace/pipeline/asr.py` | Faster-Whisper 语音识别 + Silero VAD |
| **LLM** | `wallace/pipeline/llm.py` | Ollama 流式对话、情绪标签、人格切换 |
| **TTS** | `wallace/pipeline/tts.py` | 双后端（Edge-TTS / CosyVoice）+ MP3→PCM 转码 |
| **Orchestrator** | `wallace/pipeline/orchestrator.py` | ASR→LLM→TTS 流水线编排、打断处理 |
| **Emotion** | `wallace/emotion.py` | `[mood:xxx]` 标签解析 |
| **Memory** | `wallace/memory/store.py` | 用户记忆 JSON 持久化 |
| **Sensor** | `wallace/sensor.py` | 传感器数据缓存、阈值告警 |
| **Care** | `wallace/care/scheduler.py` | APScheduler 主动关怀定时任务 |
| **MQTT** | `wallace/smarthome/mqtt.py` | 智能家居场景联动 |

## 快速开始

### 前置要求

- Python 3.11+
- [Ollama](https://ollama.ai/) (本地运行 LLM)
- CUDA 可选（GPU 加速 ASR）

### 安装

```bash
cd server

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -e .

# 安装开发依赖（测试、Lint）
pip install -e ".[dev]"

# 可选：安装唤醒词二次确认
pip install -e ".[wakeword]"
```

### 启动 Ollama

```bash
# 拉取模型（首次需要）
ollama pull deepseek-r1:8b

# 启动 Ollama 服务（默认端口 11434）
ollama serve
```

### 运行服务

```bash
cd server
uvicorn wallace.app:create_app --factory --host 0.0.0.0 --port 8000
```

服务启动后：
- WebSocket 端点：`ws://localhost:8000/ws/{user_id}`
- 健康检查：`GET http://localhost:8000/health`

## 配置

配置文件：`config/default.toml`

### 环境变量覆盖

使用 `WALLACE_` 前缀 + 双下划线分隔层级：

```bash
# 示例：切换 LLM 模型
export WALLACE_LLM__MODEL=llama3:8b

# 示例：使用 CPU 运行 ASR
export WALLACE_ASR__DEVICE=cpu
```

### 主要配置项

| 段落 | 配置项 | 默认值 | 说明 |
|------|--------|--------|------|
| `[asr]` | `model` | `large-v3-turbo` | Whisper 模型 |
| `[asr]` | `device` | `cuda` | `cuda` / `cpu` |
| `[llm]` | `model` | `deepseek-r1:8b` | Ollama 模型名 |
| `[llm]` | `max_history_turns` | `10` | 对话历史轮数 |
| `[tts]` | `default_backend` | `edge` | `edge` / `cosyvoice` |
| `[tts]` | `edge_voice` | `zh-CN-XiaoxiaoNeural` | Edge-TTS 音色 |
| `[care]` | `morning_time` | `07:30` | 早安问候时间 |
| `[sensor]` | `alert_cooldown` | `300` | 告警防抖间隔（秒） |

完整配置参考 [config/default.toml](config/default.toml)。

## WebSocket 协议

### 音频格式

所有音频传输统一为：**PCM 16kHz 16bit 单声道 小端序**

- 每帧 512 samples = 1024 bytes (32ms)
- 二进制帧仅用于音频，其他消息用 JSON 文本帧

### ESP32 → Server

| type | 说明 |
|------|------|
| `ping` | 心跳（30秒一次） |
| `audio_start` | 开始说话 |
| _(二进制帧)_ | PCM 音频数据 |
| `audio_end` | 说话结束，触发流水线 |
| `sensor` | 传感器数据上报 |
| `event` | 按钮事件（性格切换、树洞模式、摇一摇） |
| `local_cmd` | 本地识别的智能家居指令 |

### Server → ESP32

| type | 说明 |
|------|------|
| `pong` | 心跳回复 |
| `tts_start` | TTS 开始，携带 `mood` 情绪标签 |
| _(二进制帧)_ | TTS PCM 音频数据 |
| `tts_end` | TTS 结束 |
| `tts_cancel` | 用户打断，停止播放 |
| `care` | 主动关怀推送 |
| `sensor_alert` | 传感器阈值告警 |

完整协议定义见 [architecture.md](architecture.md)。

## 开发

### 目录结构

```
server/
├── config/
│   └── default.toml      # 默认配置
├── tests/
│   ├── unit/             # 单元测试
│   ├── integration/      # 集成测试
│   └── e2e/              # 端到端测试
├── wallace/
│   ├── app.py            # FastAPI 入口
│   ├── config.py         # 配置加载
│   ├── emotion.py        # 情绪解析
│   ├── sensor.py         # 传感器处理
│   ├── wakeword.py       # 唤醒词确认
│   ├── vision.py         # 图片分析（可选）
│   ├── ws/               # WebSocket
│   │   ├── handler.py    # 消息路由
│   │   ├── protocol.py   # 协议定义
│   │   └── session.py    # 会话管理
│   ├── pipeline/         # AI 流水线
│   │   ├── asr.py        # 语音识别
│   │   ├── llm.py        # 大语言模型
│   │   ├── tts.py        # 语音合成
│   │   └── orchestrator.py  # 流水线编排
│   ├── memory/           # 用户记忆
│   │   └── store.py
│   ├── care/             # 主动关怀
│   │   └── scheduler.py
│   └── smarthome/        # 智能家居
│       └── mqtt.py
└── pyproject.toml
```

### 运行测试

```bash
cd server

# 运行全部单元 + 集成测试
python -m pytest tests/unit tests/integration -v

# 运行单个测试文件
python -m pytest tests/unit/test_llm.py -v

# 运行带覆盖率报告
python -m pytest tests/unit tests/integration --cov=wallace --cov-report=term-missing

# 端到端测试（需要本地运行 Ollama）
python -m pytest tests/e2e -v
```

### 代码检查

```bash
ruff check wallace/ tests/
```

### TDD 规范

本项目采用测试驱动开发：

1. **测试即规格** — 先阅读对应测试文件，再实现代码
2. **不改测试适配代码** — 测试失败时修改源码，非测试
3. **每次修改后运行测试** — 确保所有测试通过

## 情绪系统

LLM 回复末尾携带 `[mood:xxx]` 标签，服务端提取后通过 `tts_start` 消息下发给 ESP32 切换表情。

| 情绪 | 说明 | ESP32 表现 |
|------|------|-----------|
| `happy` | 开心 | 眼睛弯成月牙，暖黄灯光 |
| `sad` | 难过 | 眼睛下垂，蓝色呼吸灯 |
| `thinking` | 思考 | 眼睛向上看，紫色流水灯 |
| `angry` | 生气 | 眉毛下压，红色闪烁 |
| `sleepy` | 困倦 | 眼睛眯起，暗淡橙色 |
| `surprised` | 惊讶 | 眼睛睁大，白色闪烁 |
| `tsundere` | 傲娇 | 斜眼微扬，粉色灯光 |
| `neutral` | 中性 | 默认表情 |

## 人格模式

通过物理按钮连按 3 下切换（ESP32 发送 `event` 消息）：

| 模式 | 说明 |
|------|------|
| `normal` | 普通友好 |
| `cool` | 高冷简洁 |
| `talkative` | 话痨健谈 |
| `tsundere` | 傲娇口是心非 |

切换时清空对话历史，避免前人格语气残留。

## 特殊功能

### 树洞模式

长按物理按钮 3 秒进入，再次长按退出。

- ESP32 发送 `event: treehouse_mode, value: true/false`
- 进入后：只做 ASR 转录，不调用 LLM、不回复、不记忆
- 用途：用户只想倾诉，Wallace 默默陪伴

### 摇一摇冷知识

摇晃设备触发随机冷知识推送。

- ESP32 检测 MPU6050 姿态变化 → 发送 `event: shake`
- 服务端调用 LLM 生成有趣冷知识 → TTS 合成 → 推送播放
- 情绪：`surprised`

### 主动关怀

通过 APScheduler 定时任务自动推送：

| 类型 | 时间 | 内容 |
|------|------|------|
| 久坐提醒 | 每 2 小时 | 提醒用户活动一下 |
| 早安问候 | 07:30 | 包含当日天气 |
| 晚安提醒 | 22:00 | 提醒早点休息 |
| 生日祝福 | 当天 | 从用户记忆读取生日 |

推送前会检查：
- 用户是否在旁边（proximity 数据）
- 流水线是否空闲（避免打断对话）

### 传感器告警

当传感器数据超过阈值时自动告警：

| 告警类型 | 触发条件 | 建议 |
|---------|----------|------|
| 空气质量差 | MQ-135 > 200 | 建议开窗通风 |
| 光线过暗 | BH1750 < 50 lux | 建议开灯 |
| 温度过高 | > 35°C | 建议开空调 |
| 温度过低 | < 10°C | 建议加衣服 |

告警防抖：同类型告警 5 分钟内不重复触发。

### 用户记忆

自动记录和使用用户信息：

```json
{
  "nickname": "小明",
  "preferences": ["喜欢听音乐"],
  "interests": ["编程", "天文"],
  "recent_topics": ["天气", "工作"],
  "important_dates": {"birthday": "03-15"},
  "interaction_count": 42,
  "first_met": "2024-01-01"
}
```

- 存储位置：`data/memory/{user_id}.json`
- 每次对话注入 LLM 上下文
- 支持同步到 ESP32 SD 卡备份

## 测试覆盖

当前测试状态（221 passed, 6 xfailed）：

```
tests/unit/          # 单元测试（mock 外部依赖）
├── test_asr.py      ✅ PCM 转换、VAD、转录
├── test_llm.py      ✅ prompt 组装、流式解析、人格切换
├── test_tts.py      ✅ 双后端、降级、帧切割
├── test_emotion.py  ✅ 8 种情绪提取、文本清洗
├── test_sensor.py   ✅ 缓存更新、告警触发、防抖
├── test_memory.py   ✅ 读写、损坏恢复、并发安全
├── test_care.py     ✅ 推送、冲突处理、天气
├── test_mqtt.py     ✅ 命令执行、场景联动
├── test_session.py  ✅ 状态机、音频缓冲
└── test_protocol.py ✅ 消息序列化

tests/integration/   # 集成测试（模块协作）
├── test_orchestrator.py  ✅ 完整流水线、打断、分句
├── test_ws_handler.py    ✅ 消息路由、连接生命周期
└── test_care_push.py     ✅ 关怀推送全链路

tests/e2e/           # 端到端测试（需要 Ollama）
├── test_ws_e2e.py        ✅ WebSocket 全链路
├── test_conversation.py  ✅ 多轮对话
├── test_interrupt.py     ✅ 打断场景
├── test_sensor_care.py   ✅ 传感器告警
├── test_reconnect.py     ✅ 重连恢复
└── ...
```

xfail 测试标记了 architecture.md 中规划但尚未实现的功能：
- 生日祝福定时任务
- MQTT 自动重连
- MQTT 状态订阅回传

## 故障排查

### Ollama 连接失败

```
LLM health check failed: Connection refused
```

解决：
1. 确认 Ollama 已启动：`ollama serve`
2. 检查端口：默认 11434，可通过 `WALLACE_LLM__BASE_URL` 修改

### ASR 模型加载慢

首次启动需下载 Whisper 模型（约 1-3GB），请耐心等待。

加速方案：
- 使用 `tiny` 或 `base` 模型：`WALLACE_ASR__MODEL=tiny`
- 使用 CPU 模式避免 CUDA 初始化：`WALLACE_ASR__DEVICE=cpu`

### Edge-TTS 网络问题

Edge-TTS 需要网络连接，如果失败会自动降级到 CosyVoice（如已配置）。

### WebSocket 连接断开

检查：
1. ESP32 心跳是否正常（每 30 秒一次 ping）
2. 超过 90 秒无心跳服务端会主动断开
3. 查看服务端日志确认断开原因

## 依赖说明

核心依赖：

| 包 | 版本 | 用途 |
|----|------|------|
| fastapi | ≥0.100 | Web 框架 |
| faster-whisper | ≥1.0 | ASR 语音识别 |
| httpx | ≥0.24 | Ollama API 调用 |
| edge-tts | ≥6.1 | TTS 语音合成 |
| miniaudio | ≥1.59 | MP3→PCM 转码 |
| aiomqtt | ≥2.0 | MQTT 客户端 |
| apscheduler | ≥3.10,<4.0 | 定时任务 |
| pydantic-settings | ≥2.0 | 配置管理 |

开发依赖：

| 包 | 用途 |
|----|------|
| pytest | 测试框架 |
| pytest-asyncio | 异步测试 |
| pytest-cov | 覆盖率 |
| pytest-httpx | mock HTTP |
| ruff | Linter |

## 许可证

GPL-3.0-or-later
