# Wallace PC Server 架构设计

## 功能职责划分（ESP32 本地 vs PC 服务端）

逐项对照 v4.2 全部功能点，明确哪些在 ESP32 本地完成、哪些需要 PC 服务端支持。

### ESP32 本地完成（不依赖 PC）

| 功能 | 模块 | 说明 |
|------|------|------|
| 唤醒词预检 | WakeNet | 本地低延迟检测，50ms 内触发 |
| 本地指令识别 | MultiNet | 「开灯」「关灯」「调亮」「几点了」「设闹钟」等简单指令 |
| I2S 录音 | INMP441 (I2S_NUM_0) | PCM 16kHz 采集，PSRAM 缓冲 |
| I2S 播放 | MAX98357A (I2S_NUM_1) | 接收 PC 推送的音频帧播放 |
| 屏幕驱动 | GC9A01 (LovyanGFX) | 眼睛动画、情绪表情、闲置动画、说话波形 |
| 眼神追踪 | VL53L0X | 距离 → 瞳孔大小/方向，纯本地逻辑 |
| RGB 灯效 | WS2812B (RMT) | 待机呼吸、聆听光环、思考流水、说话律动、低电量警告 |
| 传感器采集 | DHT20/BH1750/MQ-135/MPU6050 | I2C/ADC 周期性读取，本地缓存 |
| 触摸输入 | TTP223 | 触摸唤醒、桌面宠物交互（开心+10） |
| 物理按钮 | GPIO 0 | 连按3下切性格、长按3秒树洞模式 |
| 摇一摇检测 | MPU6050 | 本地姿态检测触发彩蛋事件 |
| 电池管理 | ADC GPIO 5 | 电压检测、低电量分级降功耗 |
| 功耗管理 | 状态机 | FULL→NORMAL→SAVING→ULTRA_LOW→SLEEP 自动切换 |
| SD 卡读写 | SPI (GPIO 14 CS) | 音效文件播放、记忆备份存储、日志 |
| 本地定时器 | RTC | 闹钟、番茄钟倒计时 |
| WiFi 连接管理 | | 唤醒时连接、待机时断开，静态 IP 加速 |
| 桌面宠物状态机 | | 开心值/能量值本地维护，触摸/喂食/玩游戏 |
| 闲置动画 | | 随机看四周、眨眼、打哈欠、哼小曲（SD卡音效） |

### 需要 PC 服务端支持

| 功能 | 交互方向 | 对应服务端模块 | 说明 |
|------|---------|--------------|------|
| 唤醒词二次确认 | ESP32 → PC → ESP32 | `wakeword.py` | 上传音频片段，openWakeWord 确认 |
| 语音识别 (ASR) | ESP32 → PC | `pipeline/asr.py` | PCM 音频流 → Faster-Whisper 转录 |
| 对话生成 (LLM) | PC 内部 | `pipeline/llm.py` | Ollama 流式生成 + 情绪标签 |
| 语音合成 (TTS) | PC → ESP32 | `pipeline/tts.py` | Edge-TTS/CosyVoice → PCM 音频帧推送 |
| 情绪提取 | PC → ESP32 | `emotion.py` | LLM 输出解析 `[mood:xxx]`，下发给 ESP32 切换表情 |
| 用户记忆 | 双向 | `memory/store.py` | PC 持久化 + 每次对话注入 LLM 上下文 |
| 传感器上下文注入 | ESP32 → PC | `pipeline/llm.py` | 传感器数据注入 LLM prompt（「当前室温26度」） |
| 环境异常提醒 | PC → ESP32 | `care/scheduler.py` | 空气差/光线暗 → LLM 生成提醒语 → TTS 推送 |
| 主动关怀 | PC → ESP32 | `care/scheduler.py` | 定时久坐/早安/晚安/生日 → LLM 生成 → TTS 推送 |
| 天气查询 | PC 内部 | `care/scheduler.py` | 早安任务获取天气 API → 注入 LLM |
| 智能家居（复杂场景） | PC → MQTT broker | `smarthome/mqtt.py` | LLM 理解意图 → MQTT 发布（「睡觉」→ 多设备联动） |
| 性格切换 | ESP32 → PC | `pipeline/llm.py` | ESP32 按钮事件 → PC 切换 LLM system prompt |
| 树洞模式 | ESP32 → PC | `pipeline/orchestrator.py` | ESP32 长按事件 → PC 只做 ASR，不调 LLM、不回复、不记忆（纯倾听） |
| 游戏：成语接龙 | 双向 | `pipeline/llm.py` | 需要 LLM 判断成语合法性 |
| 图片分析（可选） | ESP32 → PC → ESP32 | `vision.py` | OV7670 抓拍 → LLM 多模态分析 |

### 混合处理（ESP32 本地 + PC 协作）

| 功能 | ESP32 本地部分 | PC 服务端部分 |
|------|--------------|-------------|
| 唤醒词检测 | WakeNet 预检 + 立即录音（乐观执行） | openWakeWord 二次确认，失败则通知丢弃 |
| 智能家居控制 | MultiNet 识别「开灯」→ 优先 ESP32 直发 MQTT（离线可用）；PC 在线时也通知 PC 记录 | 复杂场景由 LLM 意图理解 → MQTT 多设备联动 |
| 情绪表现 | 本地驱动动画/灯效（收到 mood 立即切换） | LLM 生成情绪标签并下发 |
| 传感器 | 本地采集 + 本地阈值告警（如低电量） | 数据上报 PC 用于 LLM 上下文 + 智能提醒 |
| 记忆系统 | SD 卡存储备份 | PC JSON 主存储 + LLM 上下文注入 |
| 桌面宠物 | 本地状态机维护（开心值/能量值） | 游戏/喂食等语音交互仍走 LLM |
| 猜数字游戏 | 本地可独立运行（简单逻辑） | 也可走 LLM 实现更自然的对话式玩法 |

---

## 目录结构

```
server/
├── pyproject.toml
├── config/
│   └── default.toml
├── tests/
│   ├── conftest.py             # 共享 fixtures
│   ├── unit/                   # 单元测试（mock 所有外部依赖）
│   │   ├── test_config.py
│   │   ├── test_protocol.py
│   │   ├── test_session.py
│   │   ├── test_asr.py
│   │   ├── test_llm.py
│   │   ├── test_tts.py
│   │   ├── test_emotion.py
│   │   ├── test_sensor.py
│   │   ├── test_memory.py
│   │   ├── test_wakeword.py
│   │   ├── test_care.py
│   │   └── test_mqtt.py
│   ├── integration/            # 集成测试（模块间协作）
│   │   ├── test_orchestrator.py
│   │   ├── test_ws_handler.py
│   │   └── test_care_push.py
│   ├── e2e/                    # 端到端测试（WebSocket 全链路）
│   │   └── test_ws_e2e.py
│   └── fixtures/
│       ├── hello.pcm           # 测试用短音频（PCM 16kHz 16bit mono）
│       ├── silence_1s.pcm      # 1 秒静音（VAD 测试）
│       ├── test_config.toml    # 测试专用配置
│       └── memory_sample.json  # 测试用记忆数据
└── wallace/
    ├── __init__.py
    ├── app.py              # FastAPI app factory + lifespan
    ├── config.py           # Pydantic Settings (读取 TOML)
    ├── ws/
    │   ├── __init__.py
    │   ├── handler.py      # WebSocket endpoint + 消息路由分发
    │   ├── session.py      # Session 会话对象（聚合连接状态）
    │   └── protocol.py     # 消息类型定义
    ├── pipeline/
    │   ├── __init__.py
    │   ├── asr.py          # Faster-Whisper + Silero VAD
    │   ├── llm.py          # Ollama 客户端 + 人格/情绪 system prompt
    │   ├── tts.py          # 双 TTS 后端 (Edge-TTS + CosyVoice)
    │   └── orchestrator.py # ASR → LLM → TTS 流水线
    ├── emotion.py          # 情绪解析 ([mood:xxx] 标签)
    ├── wakeword.py         # PC 端唤醒词二次确认 (openWakeWord)
    ├── vision.py           # 图片分析 (OV7670 抓拍 → LLM 多模态，可选)
    ├── sensor.py           # 传感器数据接收、缓存、阈值判断、LLM 上下文生成
    ├── memory/
    │   ├── __init__.py
    │   └── store.py        # JSON 文件持久化用户记忆
    ├── care/
    │   ├── __init__.py
    │   └── scheduler.py    # APScheduler 主动关怀 + 天气 API
    └── smarthome/
        ├── __init__.py
        └── mqtt.py         # MQTT 智能家居接口
```

---

## WebSocket 协议完整定义

### 音频格式约定

所有 WebSocket 传输的音频统一为：**PCM 16kHz 16bit 单声道 小端序 (signed int16 LE)**

- ESP32 → Server：每帧 512 samples = 1024 bytes（32ms），录音期间持续发送
- Server → ESP32：每帧 512 samples = 1024 bytes，TTS 合成期间持续发送
- WebSocket 二进制帧 **仅用于音频**，所有非音频数据均通过 JSON 文本帧传输（包括 image 的 base64）

### 连接

- 路由：`/ws/{user_id}`
- ESP32 连接时携带 user_id，服务端据此加载记忆和个性化配置
- 连接建立后服务端创建 `Session` 对象（见下方），断开时销毁
- **重连机制**：ESP32 断连后重连时，服务端发送 `session_restore` 消息同步当前状态（人格模式、树洞模式开关、当前 TTS 后端）。断连时正在进行的流水线立即取消清理
- **心跳**：ESP32 每 30 秒发送 `{"type": "ping"}`，服务端回 `{"type": "pong"}`。超过 90 秒无心跳视为断连，服务端主动关闭 WebSocket、取消流水线任务、刷写记忆

### ESP32 → Server 消息

| type | 字段 | 触发场景 | 服务端处理 |
|------|------|---------|-----------|
| `ping` | — | 每 30 秒 | 回复 `pong`，更新心跳时间 |
| `audio_start` | — | 用户开始说话 | 准备接收音频，如正在播放则取消（打断），发送 `tts_cancel` |
| _(二进制帧)_ | PCM 16kHz 16bit | 录音中持续发送 | 缓冲 → VAD → ASR |
| `audio_end` | — | 用户停止说话 | 触发 ASR 转录 → LLM → TTS 流水线 |
| `wakeword_verify` | `audio: base64` | WakeNet 预检通过 | openWakeWord 二次确认 |
| `sensor` | `temp, humidity, light, air_quality` | 周期上报（10s） | 缓存最新值，注入 LLM 上下文，触发阈值告警 |
| `proximity` | `distance, user_present: bool` | 距离变化显著时上报（非周期） | 判断用户是否在旁边，用于关怀推送前置检查 |
| `device_state` | `battery_pct, power_mode, wifi_rssi` | 状态变化时上报 | 低电量提醒，连接质量监控 |
| `event` | `event: "personality_switch", value: "tsundere"` | 物理按钮连按3下 | 切换 LLM system prompt 人格 |
| `event` | `event: "treehouse_mode", value: true/false` | 物理按钮长按3秒 | 切换树洞模式（只 ASR 不回复不记录） |
| `event` | `event: "shake"` | MPU6050 摇一摇 | LLM 生成随机冷知识 → TTS 推送 |
| `event` | `event: "touch"` | TTP223 触摸 | 可选：服务端记录交互，或纯本地处理 |
| `local_cmd` | `action: "light_on"` | MultiNet 本地识别智能家居指令 | 转发 MQTT 执行 |
| `image` | `data: base64` | OV7670 抓拍 | LLM 多模态分析（可选） |
| `config` | `tts_backend: "edge\|cosyvoice"` | 用户切换 TTS | 切换 TTS 后端 |

### Server → ESP32 消息

| type | 字段 | 触发场景 | ESP32 处理 |
|------|------|---------|-----------|
| `wakeword_result` | `confirmed: bool` | 唤醒词二次确认结果 | false 则丢弃已录内容 |
| `tts_start` | `mood: "happy"` | TTS 音频即将开始 | 切换对应情绪表情 + 灯效 |
| _(二进制帧)_ | PCM 音频 | TTS 合成中持续推送 | I2S 播放 |
| `tts_cancel` | — | 用户打断（收到新 audio_start） | 立即停止 I2S 播放，清空音频缓冲 |
| `tts_end` | — | TTS 播放结束 | 恢复闲置状态 |
| `pong` | — | 回应 ESP32 心跳 | 更新连接状态 |
| `session_restore` | `personality, treehouse, tts_backend` | ESP32 重连成功 | 恢复服务端当前状态到 ESP32 |
| `text` | `content, partial: bool, mood?` | ASR 转录结果（`partial=false`）或 LLM 流末尾最终文本（携带 mood） | 可选：屏幕显示文字 |
| `care` | `content, mood` | 主动关怀触发 | 播放 TTS 音频 + 切换表情 |
| `command_result` | `action, success, message` | MQTT 执行结果 | 可选：语音反馈「灯已打开」 |
| `memory_sync` | `data: {...}` | 记忆更新后 | ESP32 备份到 SD 卡 |
| `sensor_alert` | `alert: "air_quality_bad", suggestion: "..."` | 传感器阈值触发 | 播放提醒语音 |

---

## 核心模块设计

### 0. ws/session.py — 会话对象（贯穿所有模块）

每个 WebSocket 连接对应一个 `Session` 实例，聚合该连接的所有状态：

```python
class Session:
    user_id: str
    ws: WebSocket
    # 状态
    personality: str = "normal"       # normal/cool/talkative/tsundere
    treehouse_mode: bool = False
    tts_backend: str = "edge"         # edge/cosyvoice
    # 流水线
    pipeline_task: asyncio.Task | None  # 当前流水线 asyncio.Task，用于 cancel
    pipeline_lock: asyncio.Lock         # 防止多个流水线并发
    audio_buffer: bytearray             # 录音缓冲
    wakeword_confirmed: asyncio.Event   # 唤醒词确认信号
    # 缓存
    sensor_cache: SensorData            # 最新传感器值
    proximity_present: bool = True      # 用户是否在旁边（默认在）
    last_heartbeat: float               # 最后心跳时间戳
    # 对话
    chat_history: list                  # 对话历史（受 max_turns 限制）
    memory: UserMemory                  # 加载的用户记忆
```

- `app.py` 维护全局 `sessions: dict[str, Session]`，scheduler/sensor 模块通过此字典获取 WebSocket 引用
- Session 在连接建立时创建（加载 memory），断开时销毁（flush memory）

### 1. config.py — 配置管理
- 使用 Pydantic Settings 从 `config/default.toml` 加载
- 分段及关键字段：

```toml
[server]
host = "0.0.0.0"
port = 8000
log_level = "INFO"              # DEBUG/INFO/WARNING

[asr]
model = "large-v3-turbo"
device = "cuda"                 # cuda/cpu
compute_type = "float16"        # float16/int8
language = "zh"
vad_threshold = 0.5             # Silero VAD 灵敏度

[llm]
base_url = "http://localhost:11434"
model = "deepseek-r1:8b"
temperature = 0.7
max_tokens = 512
max_history_turns = 10          # 对话历史窗口
health_check_interval = 60      # 秒

[tts]
default_backend = "edge"        # edge/cosyvoice
edge_voice = "zh-CN-XiaoxiaoNeural"
cosyvoice_url = "http://localhost:9880"
cosyvoice_voice = "default"

[mqtt]
broker = "localhost"
port = 1883
username = ""
password = ""
topic_prefix = "wallace/home"   # 智能家居 topic 前缀
reconnect_interval = 5          # 秒

[care]
sedentary_interval_hours = 2
morning_time = "07:30"
evening_time = "22:00"

[sensor]
report_interval = 10            # ESP32 上报周期（秒）
alert_cooldown = 300            # 告警防抖间隔（秒）
air_quality_threshold = 200     # MQ-135 阈值
light_dark_threshold = 50       # BH1750 低光阈值 (lux)
temp_high = 35                  # 温度高阈值 (°C)
temp_low = 10                   # 温度低阈值 (°C)
proximity_default_present = true  # 无数据时默认用户在旁边

[weather]
api_url = "https://api.seniverse.com/v3/weather/now.json"
api_key = ""
city = "beijing"
```

- 环境变量覆盖：`WALLACE_` 前缀（如 `WALLACE_LLM__MODEL`）

### 2. app.py — FastAPI 应用
- **lifespan 启动顺序**（有依赖关系）：
  1. 加载配置
  2. 初始化日志（`logging.basicConfig`，级别来自 config，格式 `%(asctime)s %(name)s %(levelname)s %(message)s`）
  3. `await asyncio.to_thread(load_asr_model)` — 阻塞加载 Whisper 模型
  4. 初始化 LLM 客户端（httpx.AsyncClient）+ 首次健康检查
  5. 初始化 TTS 引擎
  6. 连接 MQTT broker
  7. 启动 APScheduler
  8. 初始化全局 `sessions: dict[str, Session]`
- **lifespan 关闭顺序**：
  1. 停止 APScheduler
  2. 遍历所有 session：取消流水线、flush 记忆、关闭 WebSocket
  3. 断开 MQTT
  4. 关闭 httpx client
- 挂载 WebSocket 路由 `/ws/{user_id}`（按用户隔离会话与记忆）
- 健康检查 `GET /health`（返回各子系统状态：ASR loaded、LLM reachable、MQTT connected）

### 3. ws/handler.py — WebSocket 消息路由
- 接收消息后按 `type` 字段分发到对应处理器：
  - `audio_start/end` + 二进制帧 → `orchestrator`
  - `wakeword_verify` → `wakeword.py`
  - `sensor` → `sensor.py`
  - `device_state` → 更新连接状态缓存
  - `event` → 按 event 类型路由（personality_switch → llm, treehouse → orchestrator, shake → llm）
  - `local_cmd` → `smarthome/mqtt.py`
  - `image` → `vision.py`
  - `config` → 运行时配置切换

### 4. pipeline/asr.py — 语音识别
- Faster-Whisper (CTranslate2)，模型 `large-v3-turbo`（v4.2 文档指定）
- **模型加载**：`WhisperModel()` 是阻塞调用（5-30s），在 lifespan 中通过 `asyncio.to_thread()` 加载
- **VAD + 录音流程**：
  1. `audio_start` 到达 → 开始向 `session.audio_buffer` 追加二进制帧
  2. 可选：Silero VAD 对每个 chunk 做流式检测，连续 1s 静音则自动截断（等效 `audio_end`）
  3. `audio_end` 到达 → 将 `audio_buffer` 转为 numpy float32 归一化：`np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0`
  4. 调用 `model.transcribe(audio_array, language="zh")` — **此方法阻塞 CPU**，必须通过 `asyncio.to_thread()` 调用
  5. 返回转录文本
- 输入：`session.audio_buffer` (PCM int16 LE) → 输出：转录文本字符串

### 5. pipeline/llm.py — 大语言模型
- Ollama HTTP API (`/api/chat`)，流式输出，默认模型 `deepseek-r1:8b`
- **健康检查**：启动时 + 定期（60s）ping Ollama `/api/tags`，不可用时向 ESP32 推送语音提示「大脑暂时离线」
- **System prompt 组装**：Wallace 人格基础 prompt + 当前情绪标签指令 + 记忆摘要 + 传感器上下文
- 人格模式（v4.2 §8.4）：普通、高冷、话痨、傲娇，通过切换 system prompt 实现。**切换时清空对话历史**（避免前人格语气残留）
- 对话历史窗口（可配置轮数）
- **情绪解析**：正则 `\[mood:(\w+)\]`，从完整回复中提取（非流式阶段）。LLM system prompt 要求将标签放在回复最末尾。若未匹配到则默认 `neutral`（ESP32 保持当前表情不变）
- 情绪枚举（对齐 v4.2 §5.1）：`happy`、`sad`、`thinking`、`angry`、`sleepy`、`surprised`、`tsundere`、`neutral`(默认)
- 树洞模式：收到 treehouse 事件后，只做 ASR 记录，不调用 LLM 也不记忆

### 6. pipeline/tts.py — 语音合成（双后端）
- `TTSBackend` 协议：`async def synthesize(text, voice) -> AsyncIterator[bytes]`
- **EdgeTTSBackend**：调用 edge-tts，默认 `zh-CN-XiaoxiaoNeural`，低延迟
  - ⚠️ edge-tts 输出 MP3 格式，需转码为 PCM 16kHz 16bit 单声道
  - **转码方案**：edge-tts 按句合成，每句产出完整 MP3 数据（非流式碎片），使用 `miniaudio.decode(mp3_bytes, sample_rate=16000, nchannels=1)` 整句解码后切割为 1024 byte 帧发送。不需要处理流式 MP3 碎片拼接
- **CosyVoiceBackend**：调用本地 CosyVoice 2 HTTP API，支持方言（四川话、东北话等）
  - CosyVoice 可直接输出 PCM，无需转码
- **后端降级**：Edge-TTS 调用失败（网络问题）→ 自动降级到 CosyVoice；两者均失败 → 向 ESP32 发送错误提示文本
- 运行时可通过 WebSocket config 消息切换后端

### 7. pipeline/orchestrator.py — 流水线编排

**状态机**：每个 Session 的流水线有明确状态：`IDLE` → `RECORDING` → `PROCESSING` → `SPEAKING` → `IDLE`

- `async def process(session: Session)`:
  1. **ASR 转录**：`await asyncio.to_thread(asr.transcribe, session.audio_buffer)`
  2. **记忆注入 + 传感器上下文注入**：组装 LLM messages
  3. **LLM 生成（流式）**：通过 httpx 流式读取 Ollama 响应
  4. **流式分句 + TTS**：LLM token 累积到 `sentence_buffer`，遇到句末标点（`。！？；\n`）时：
     - 提取该句文本，送入 TTS 合成
     - 第一句合成前发送 `tts_start`（此时 mood 用默认值 `thinking`）
     - TTS 产出的 PCM 帧逐帧通过 WebSocket 二进制帧推送
  5. **情绪提取**：LLM 流结束后，从完整回复提取 `[mood:xxx]`，补发 `text` 消息携带最终 mood
  6. 最后一句 TTS 完成 → 发送 `tts_end`
  7. **更新记忆**：从对话内容中提取关键信息（关键词匹配，非额外 LLM 调用），更新 memory
  8. 状态回到 `IDLE`

- **打断处理**：任何状态下收到新 `audio_start`：
  1. `session.pipeline_task.cancel()` — asyncio 取消当前协程
  2. 协程内捕获 `CancelledError`，执行清理：关闭 httpx stream、停止 TTS 生成器
  3. 向 ESP32 发送 `tts_cancel`
  4. 状态重置为 `RECORDING`，开始接收新音频
  5. 使用 `session.pipeline_lock` 确保同一时间只有一个流水线在运行

- 树洞模式：只执行步骤 1（ASR），转录文本仅 log 不回复不记忆

- **唤醒词 + 录音协调**：`audio_start` 可能与 `wakeword_verify` 同时到达。处理逻辑：
  - 收到 `audio_start` → 开始缓冲音频，但不立即触发 ASR
  - 若有 pending 的 wakeword 确认 → 等待 `session.wakeword_confirmed` Event（最多 2s）
  - 确认失败 → 清空 buffer，回到 IDLE；确认成功或超时 → 继续正常流程

### 8. sensor.py — 传感器数据处理（新增）
- 接收 ESP32 周期上报的传感器数据，缓存最新值
- **LLM 上下文生成**：将传感器数据格式化为自然语言注入 prompt（「当前室温26°C，湿度60%，光线较暗」）
- **阈值告警**（可配置）：
  - 空气质量差（MQ-135 > 阈值）→ 生成提醒
  - 光线过暗（BH1750 < 阈值）→ 建议开灯
  - 温度异常 → 提醒
- **告警防抖**：同类型告警最短间隔 5 分钟（可配置），避免重复打扰
- 告警推送复用 care 的冲突处理逻辑：检查 `session.pipeline_lock`，忙则排队等待
- 告警通过 LLM 生成自然语言 → TTS 推送

### 9. memory/store.py — 用户记忆
- JSON 文件存储：`data/memory/{user_id}.json`（按用户隔离）
- 存储字段（对齐 v4.2 §6.1）：用户昵称、偏好、兴趣、最近 5 个话题、重要日期（生日等）、交互次数、首次见面时间
- LLM 上下文注入：每次对话前将记忆摘要拼入 system prompt
- 记忆更新后通过 `memory_sync` 消息通知 ESP32 备份到 SD 卡
- **同步策略**：增量同步，最多每 5 分钟一次（避免频繁 SPI 写入），仅推送变更字段

### 10. care/scheduler.py — 主动关怀
- APScheduler 3.x `AsyncIOScheduler`（注意：4.x API 完全不同，使用 3.x 稳定版）
- **依赖注入**：初始化时传入 `sessions` 字典引用，任务执行时遍历在线 session 推送
- 定时任务（对齐 v4.2 §6.2）：
  - 每 2 小时：久坐提醒（mood: caring）
  - 每天 7:30：早安 + 天气播报（mood: happy）— 调用天气 API 获取当地天气
  - 每天 22:00：晚安提醒（mood: gentle）
  - 特殊日期：生日/纪念日祝福（mood: excited），从 memory 读取
- 传感器触发：空气差/温度异常 → 生成环境提醒
- 通过 WebSocket 主动推送：LLM 生成关怀文本 → TTS 合成 → 音频帧推送
- **冲突处理**：推送前检查 orchestrator 是否正在处理用户对话，若是则排队等待（最多等 30s，超时丢弃）
- **前置检查**：检查 `proximity` 最近数据，用户不在旁边则跳过推送
- 依赖：检查 ESP32 是否在线（WebSocket 连接状态），离线则跳过

### 11. smarthome/mqtt.py — 智能家居
- aiomqtt 客户端（需处理断线重连：捕获 `MqttError` 后重建 `Client` 实例并重新订阅）
- **Topic 格式**：`{topic_prefix}/{device_type}/{action}`，如 `wallace/home/light/on`，payload 为 JSON `{"brightness": 80}`
- **两种触发路径**：
  - ESP32 MultiNet 本地识别 → `local_cmd` 消息 → 直接 MQTT 执行（低延迟）
  - LLM 对话理解 → 复杂场景联动 → MQTT 多设备执行
- 订阅状态反馈 → 通过 `command_result` 返回 ESP32
- 场景联动（v4.2 §7.2）：「睡觉」→ 关灯+空调睡眠+晚安语音，「起床」→ 灯光渐亮+早安

### 12. wakeword.py — 唤醒词二次确认（v4.2 §4.2 混合策略）
- ESP32 本地 WakeNet 预检后，音频片段上传 PC 端
- 使用 openWakeWord 做高精度二次确认
- **模型**：openWakeWord 自带英文模型，中文唤醒词「嗨华莱士」需自行训练或使用通用 VAD 替代。初期可跳过二次确认，仅用 WakeNet
- **超时机制**：2 秒内未返回结果则默认确认通过（避免阻塞用户说话）
- 确认通过 → 返回 `wakeword_result`，ESP32 继续录音；失败 → 丢弃

### 13. vision.py — 多模态图片分析（v4.2 §6.3，可选）
- 接收 ESP32 OV7670 抓拍的 base64 图片
- 转发 LLM 多模态接口分析（人脸检测、场景描述）
- 结果用于调整眼神方向或语音回复

---

## 测试策略

### 基础设施

- 框架：**pytest** + **pytest-asyncio**（`asyncio_mode = "auto"`）
- 覆盖率：**pytest-cov**，目标 ≥ 80%（`pytest --cov=wallace --cov-report=term-missing`）
- CI 运行：`pytest tests/unit tests/integration -v`（不依赖 GPU、网络或外部服务）
- 端到端测试需本地启动 Ollama，标记 `@pytest.mark.e2e`，CI 中跳过

### conftest.py 共享 Fixtures

```python
# 测试配置（覆盖默认值，使用 CPU、小超时等）
@fixture
def test_config() -> Settings: ...

# mock WebSocket（记录发送的消息，可注入接收消息）
@fixture
def mock_ws() -> MockWebSocket: ...

# 预构建 Session（挂载 mock_ws，已加载测试记忆）
@fixture
def session(mock_ws, test_config) -> Session: ...

# mock ASR 模型（返回固定转录文本）
@fixture
def mock_asr() -> MagicMock: ...

# mock Ollama（返回可控的流式 token 序列）
@fixture
def mock_ollama(httpx_mock) -> None: ...

# mock TTS（返回固定 PCM 帧序列）
@fixture
def mock_tts() -> MagicMock: ...

# mock MQTT client
@fixture
def mock_mqtt() -> AsyncMock: ...

# 生成测试用 PCM 音频 bytes
@fixture
def pcm_audio() -> bytes: ...
```

### 单元测试详细用例

#### test_config.py — 配置管理
| 用例 | 验证点 |
|------|--------|
| 加载 default.toml | 所有字段有默认值，类型正确 |
| 环境变量覆盖 | `WALLACE_LLM__MODEL=xxx` 覆盖 `llm.model` |
| 缺失必填字段 | 缺少 `[llm]` 段时抛出 `ValidationError` |
| 无效值 | `asr.device = "tpu"` 等非法枚举值报错 |
| test_config.toml | 测试配置加载成功（CPU 模式、小超时） |

#### test_protocol.py — 消息协议
| 用例 | 验证点 |
|------|--------|
| 每种 ESP32→Server 消息 | JSON 序列化/反序列化往返一致 |
| 每种 Server→ESP32 消息 | JSON 序列化/反序列化往返一致 |
| 未知 type | 反序列化时抛出明确错误（不静默忽略） |
| 字段缺失 | 缺少必填字段时 Pydantic ValidationError |
| event 子类型 | personality_switch / treehouse_mode / shake / touch 各自验证 |

#### test_session.py — 会话对象
| 用例 | 验证点 |
|------|--------|
| 创建 Session | 默认状态正确（personality=normal, treehouse=False, IDLE） |
| pipeline_lock | 两个协程竞争 lock，只有一个能进入 |
| audio_buffer | 追加二进制帧、清空、转 numpy 归一化 |
| wakeword_confirmed Event | set/wait/clear 行为正确 |
| 状态机转换 | IDLE→RECORDING→PROCESSING→SPEAKING→IDLE 合法路径 |
| 非法状态转换 | IDLE→SPEAKING 等非法路径抛出异常 |

#### test_asr.py — 语音识别
| 用例 | 验证点 |
|------|--------|
| PCM→numpy 转换 | int16 LE → float32 归一化到 [-1.0, 1.0] |
| 空音频 | 空 buffer → 返回空字符串（不崩溃） |
| 极短音频（<0.5s） | 正常处理或返回空（不抛异常） |
| transcribe 在线程中调用 | 验证 `asyncio.to_thread` 被调用（不阻塞事件循环） |
| VAD 静音检测 | 全静音音频 → VAD 判定无语音 → 跳过 ASR |
| mock 模型返回 | mock `WhisperModel.transcribe` 返回固定文本 |

#### test_llm.py — 大语言模型
| 用例 | 验证点 |
|------|--------|
| system prompt 组装 | 包含人格 prompt + 记忆摘要 + 传感器上下文 |
| 流式输出解析 | mock Ollama 流式 JSON lines → 逐 token 提取 |
| 情绪解析 - 正常 | `"好的[mood:happy]"` → mood=happy, text="好的" |
| 情绪解析 - 缺失 | `"好的"` → mood=neutral |
| 情绪解析 - 非法值 | `"[mood:xxx]"` → mood=neutral（不在枚举中回退默认） |
| 人格切换 | 切换到 tsundere → system prompt 更新，chat_history 清空 |
| 对话历史窗口 | 超过 max_history_turns 时截断最早的轮次 |
| 健康检查成功 | mock `/api/tags` 200 → healthy |
| 健康检查失败 | mock `/api/tags` 超时/500 → unhealthy，触发通知 |
| 树洞模式 | treehouse=True 时不调用 Ollama |

#### test_tts.py — 语音合成
| 用例 | 验证点 |
|------|--------|
| EdgeTTS 合成 | mock edge-tts → 返回 MP3 bytes |
| MP3→PCM 转码 | 已知 MP3 → miniaudio 解码 → 验证输出为 16kHz 16bit mono |
| PCM 帧切割 | 解码后的 PCM 按 1024 bytes 切割，最后一帧可能 < 1024（补零） |
| CosyVoice 合成 | mock HTTP API → 返回 PCM bytes |
| 后端切换 | edge → cosyvoice → edge，每次切换后合成走正确后端 |
| Edge-TTS 降级 | mock edge-tts 抛异常 → 自动降级到 CosyVoice |
| 双后端均失败 | 两者都抛异常 → 返回错误文本（不崩溃） |
| 空文本 | 空字符串输入 → 不调用 TTS，返回空迭代器 |

#### test_emotion.py — 情绪解析
| 用例 | 验证点 |
|------|--------|
| 所有合法情绪 | 8 种枚举值逐一测试提取 |
| 标签位置 | 末尾 / 中间（只取最后一个） / 开头 |
| 多个标签 | `"[mood:sad]...[mood:happy]"` → 取最后一个 happy |
| 文本清洗 | 提取后原文中 `[mood:xxx]` 被移除 |

#### test_sensor.py — 传感器处理
| 用例 | 验证点 |
|------|--------|
| 数据缓存更新 | 收到 sensor 消息 → cache 更新为最新值 |
| LLM 上下文生成 | cache 有值 → 生成自然语言字符串（含温度/湿度/光线/空气） |
| LLM 上下文 - 无数据 | cache 为空 → 返回空字符串（不注入） |
| 阈值告警 - 空气差 | air_quality > threshold → 触发告警 |
| 阈值告警 - 光线暗 | light < threshold → 触发告警 |
| 告警防抖 | 同类型告警 5 分钟内第二次 → 不触发 |
| 告警防抖过期 | 超过 cooldown → 再次触发 |
| proximity 更新 | distance 消息更新 `session.proximity_present` |
| proximity 默认值 | 从未收到 proximity → 使用配置默认值 |

#### test_memory.py — 用户记忆
| 用例 | 验证点 |
|------|--------|
| 加载已有记忆 | JSON 文件存在 → 正确反序列化 |
| 加载空记忆 | 文件不存在 → 创建默认空记忆 |
| 保存记忆 | 修改字段 → save → 重新 load → 一致 |
| JSON 文件损坏 | 非法 JSON → 日志告警，加载默认空记忆（不崩溃） |
| 并发写入安全 | 两个协程同时 save → 文件不损坏（使用写入临时文件 + rename） |
| 记忆字段完整 | 所有 v4.2 §6.1 字段存在 |
| 增量同步节流 | 5 分钟内多次更新 → 只触发一次 memory_sync |
| 变更检测 | 无变更 → 不触发 sync |

#### test_wakeword.py — 唤醒词二次确认
| 用例 | 验证点 |
|------|--------|
| 确认通过 | mock openWakeWord 返回高置信度 → confirmed=True |
| 确认失败 | 低置信度 → confirmed=False |
| 超时默认通过 | mock 延迟 3 秒 → 2 秒超时 → confirmed=True |
| base64 解码 | 验证音频从 base64 正确解码为 PCM |

#### test_care.py — 主动关怀
| 用例 | 验证点 |
|------|--------|
| 久坐提醒触发 | 手动触发 job → 调用 LLM + TTS + WebSocket 发送 |
| 早安含天气 | mock 天气 API → 天气数据注入 LLM prompt |
| 天气 API 失败 | mock 超时 → 早安不含天气但仍正常推送 |
| 生日祝福 | memory 中 birthday 匹配今天 → 触发 |
| ESP32 离线 | session 不存在 → 跳过推送（不报错） |
| 用户不在旁边 | proximity_present=False → 跳过推送 |
| 冲突排队 | pipeline_lock 被占 → 等待后推送 |
| 冲突超时丢弃 | pipeline_lock 被占超过 30s → 丢弃 |

#### test_mqtt.py — 智能家居
| 用例 | 验证点 |
|------|--------|
| local_cmd 转发 | `action: "light_on"` → MQTT publish 到正确 topic |
| 场景联动 | `action: "sleep"` → 多条 MQTT 消息（关灯+空调+…） |
| MQTT 断连重连 | mock 断连 → 捕获异常 → 重建 client |
| command_result 回传 | MQTT 订阅回调 → 构造 command_result → 发送 ESP32 |
| broker 不可用 | 启动时连接失败 → 日志告警，MQTT 功能降级（不影响其他模块） |

### 集成测试详细用例

#### test_orchestrator.py — 流水线编排
| 用例 | 验证点 |
|------|--------|
| 完整链路 | PCM → ASR → LLM → TTS → WebSocket 发送序列正确 |
| 发送顺序验证 | 收到的消息顺序：`tts_start` → 二进制帧(多个) → `text`(含mood) → `tts_end` |
| 流式分句 | LLM 输出 "你好。世界！" → TTS 被调用 2 次（两句） |
| 分句边界 | 验证 `。！？；\n` 各标点都能正确断句 |
| 句末无标点 | LLM 输出无标点文本 → 流结束后整体作为一句送 TTS |
| 打断 - PROCESSING | LLM 生成中收到 audio_start → 取消 LLM → 发 tts_cancel |
| 打断 - SPEAKING | TTS 播放中收到 audio_start → 取消 TTS → 发 tts_cancel |
| 打断后恢复 | 打断 → 新录音 → 新流水线正常完成 |
| 树洞模式 | treehouse=True → ASR 完成后不调 LLM/TTS |
| 状态机完整性 | 正常流程和打断流程中状态转换均正确 |
| ASR 返回空 | ASR 转录为空 → 不调 LLM，直接回 IDLE |
| LLM 返回空 | LLM 无输出 → 不调 TTS，直接回 IDLE |

#### test_ws_handler.py — WebSocket 消息路由
| 用例 | 验证点 |
|------|--------|
| JSON 消息路由 | 各 type 消息分发到正确处理器 |
| 二进制帧路由 | 二进制消息 → 追加到 session.audio_buffer |
| 未知 type | 未知消息类型 → 日志 warning，不崩溃 |
| JSON 解析失败 | 非法 JSON 文本帧 → 日志 warning，不断开连接 |
| 心跳处理 | ping → 回复 pong + 更新 last_heartbeat |
| 连接建立 | 新连接 → 创建 Session + 加载记忆 + 启动心跳监控 |
| 连接断开 | 断开 → 取消流水线 + flush 记忆 + 移除 session |
| 重连 | 同一 user_id 重连 → 发送 session_restore |

#### test_care_push.py — 关怀推送集成
| 用例 | 验证点 |
|------|--------|
| 关怀全链路 | scheduler 触发 → LLM 生成文本 → TTS 合成 → WebSocket 发送 care + 音频 |
| 传感器告警全链路 | sensor 超阈值 → LLM 生成 → TTS → WebSocket 发送 sensor_alert + 音频 |

### 端到端测试 (e2e)

#### test_ws_e2e.py — WebSocket 全链路（需标记 `@pytest.mark.e2e`）
| 用例 | 验证点 |
|------|--------|
| 对话往返 | TestClient 连接 → 发 audio_start + PCM + audio_end → 收到 tts_start + 音频帧 + tts_end |
| 打断往返 | 播放中发 audio_start → 收到 tts_cancel |
| 多轮对话 | 连续 3 轮对话 → 对话历史正确累积 |
| sensor + care | 发 sensor 数据 → 触发告警 → 收到 sensor_alert |
| 性格切换 | 发 personality_switch → 后续对话 system prompt 已更新 |

### 测试用 dev 依赖

```
pytest
pytest-asyncio
pytest-cov
pytest-httpx          # mock httpx 请求（Ollama API、天气 API、CosyVoice API）
pytest-timeout        # 防止异步测试挂死（默认 10s 超时）
freezegun             # 冻结时间（care 定时任务、告警防抖、memory sync 节流）
```

## 依赖 (pyproject.toml)

```
fastapi, uvicorn[standard], websockets
faster-whisper, silero-vad (torch)
httpx (Ollama API + 天气 API)
edge-tts
miniaudio (MP3→PCM 转码，用于 Edge-TTS 输出)
openwakeword (唤醒词二次确认)
pydantic-settings (Python 3.11+ 使用内置 tomllib，无需 tomli)
numpy
aiomqtt
apscheduler>=3.10,<4.0

# dev
pytest, pytest-asyncio, pytest-cov
pytest-httpx, pytest-timeout, freezegun
```

## 实现顺序

1. **项目骨架**：pyproject.toml、config、app.py、基础 WebSocket（含 `/ws/{user_id}` + 消息路由）
2. **协议定义**：protocol.py 所有消息类型 Pydantic 模型
3. **ASR 模块**：Faster-Whisper large-v3-turbo + Silero VAD
4. **LLM 模块**：Ollama 流式对话（deepseek-r1:8b）+ 情绪枚举 + 情绪解析 + 人格切换
5. **TTS 模块**：Edge-TTS 后端（先单后端跑通）
6. **流水线编排**：串联 ASR → LLM → TTS，WebSocket 全链路 + 打断
7. **传感器处理**：sensor.py 数据缓存 + LLM 上下文注入 + 阈值告警
8. **唤醒词二次确认**：openWakeWord 集成
9. **CosyVoice 后端**：添加第二 TTS 后端 + 切换机制
10. **记忆系统**：用户记忆 JSON 持久化 + LLM 上下文注入 + SD 卡同步
11. **主动关怀**：APScheduler 定时任务（久坐/早安/晚安/纪念日）+ 天气 API
12. **智能家居**：MQTT 场景联动 + local_cmd 直通
13. **彩蛋支持**：性格切换、树洞模式、摇一摇冷知识
14. **多模态（可选）**：OV7670 图片接收 + LLM 分析
