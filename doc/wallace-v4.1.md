# Wallace v4.1：拟人化桌面 AI 机器人

> **目标**：构建一个具备"听、说、看、感知、情感"能力的桌面语音助手，让 AI 真正"活"起来。  
> **架构**：ESP32-S3（N16R8）单芯片全栈方案 + PC 服务端协同处理。  
> **版本更新**：v4.1 完善开源唤醒词方案、补充 PlatformIO 配置示例、优化混合唤醒策略说明。

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 系统架构](#2-系统架构)
  - [2.1 硬件链路](#21-硬件链路)
  - [2.2 数据流向（语音唤醒模式）](#22-数据流向语音唤醒模式)
- [3. 硬件设计与引脚规划](#3-硬件设计与引脚规划)
  - [3.1 核心模块引脚](#31-核心模块引脚)
  - [3.2 扩展模块引脚](#32-扩展模块引脚)
- [4. 软件实现路线](#4-软件实现路线)
  - [4.1 固件端（ESP32-S3）](#41-固件端esp32-s3)
  - [4.2 语音唤醒方案](#42-语音唤醒方案)
  - [4.3 服务端（PC）](#43-服务端pc)
- [5. 拟人化体验设计](#5-拟人化体验设计)
  - [5.1 情绪系统](#51-情绪系统)
  - [5.2 眼神追踪](#52-眼神追踪)
  - [5.3 闲置动画](#53-闲置动画)
  - [5.4 呼吸灯效果](#54-呼吸灯效果)
- [6. AI 能力扩展](#6-ai-能力扩展)
  - [6.1 记忆系统](#61-记忆系统)
  - [6.2 主动关怀](#62-主动关怀)
  - [6.3 多模态输入](#63-多模态输入)
  - [6.4 本地指令识别](#64-本地指令识别)
- [7. 环境感知与智能家居](#7-环境感知与智能家居)
  - [7.1 环境传感器](#71-环境传感器)
  - [7.2 智能家居联动](#72-智能家居联动)
- [8. 趣味玩法](#8-趣味玩法)
  - [8.1 小游戏模式](#81-小游戏模式)
  - [8.2 桌面宠物模式](#82-桌面宠物模式)
  - [8.3 实用工具](#83-实用工具)
  - [8.4 彩蛋功能](#84-彩蛋功能)
- [9. 电源管理策略](#9-电源管理策略)
  - [9.1 供电架构](#91-供电架构)
  - [9.2 功耗预估与续航](#92-功耗预估与续航)
  - [9.3 低功耗优化策略](#93-低功耗优化策略)
- [10. 硬件采购清单（BOM）](#10-硬件采购清单bom)
  - [10.1 核心模块（必选）](#101-核心模块必选)
  - [10.2 扩展模块（可选）](#102-扩展模块可选)
  - [10.3 采购注意事项](#103-采购注意事项)
- [11. 已知问题与解决方案](#11-已知问题与解决方案)
- [12. 硬件形态创意](#12-硬件形态创意)
- [13. 开发路线图](#13-开发路线图)
- [附录 A：市场方案对比参考](#附录-a市场方案对比参考)
- [附录 B：开发调试建议](#附录-b开发调试建议)

---

## 1. 项目概述

### 核心体验

| 能力 | 描述 | 实现方式 |
|------|------|----------|
| **听** | 语音唤醒 + 语音采集 | ESP32-S3 本地运行唤醒词模型，持续监听 |
| **说** | 自然语音回复 | PC 端 LLM 生成文本，TTS 合成语音回传播放 |
| **看** | 圆形屏幕模拟眼睛 | 眨眼、注视、情绪表情等拟人化动效 |
| **感知** | 环境与用户感知 | 温湿度、光线、距离、人脸检测（可选） |
| **情感** | 情绪状态系统 | 根据对话内容展示喜怒哀乐等情绪 |
| **续航** | 电池供电，语音唤醒待机 | 预计 3-5 天待机（2500mAh 电池） |

### v4 版本新增特性

```
┌─────────────────────────────────────────────────────────────────┐
│  v4 新增特性                                                    │
├─────────────────────────────────────────────────────────────────┤
│  🎭 拟人化升级                                                  │
│     ├── 情绪系统（喜怒哀乐表情）                                │
│     ├── 眼神追踪（跟随用户方位）                                │
│     ├── 闲置动画（自主行为）                                    │
│     └── RGB 呼吸灯状态反馈                                      │
├─────────────────────────────────────────────────────────────────┤
│  🧠 AI 能力扩展                                                 │
│     ├── 记忆系统（记住用户偏好）                                │
│     ├── 主动关怀（定时提醒、天气预警）                          │
│     ├── 多模态输入（可选摄像头）                                │
│     └── 本地指令识别（简单命令无需联网）                        │
├─────────────────────────────────────────────────────────────────┤
│  🏠 环境感知与智能家居                                          │
│     ├── 温湿度/光线/空气质量传感器                              │
│     └── MQTT/HTTP 智能家居控制                                  │
├─────────────────────────────────────────────────────────────────┤
│  🎮 趣味玩法                                                    │
│     ├── 小游戏（猜数字、成语接龙）                              │
│     ├── 桌面宠物模式                                            │
│     └── 隐藏彩蛋                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 系统架构

### 2.1 硬件链路

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ESP32-S3 N16R8                              │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐           │
│  │ WakeNet   │ │ Audio     │ │ Display   │ │ Sensors   │           │
│  │ 唤醒检测  │ │ I2S 音频  │ │ SPI 屏幕  │ │ I2C 传感  │           │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘           │
└────────┼─────────────┼─────────────┼─────────────┼──────────────────┘
         │             │             │             │
   ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
   │ INMP441   │ │ MAX98357A │ │ GC9A01    │ │ VL53L0X   │
   │ 麦克风    │ │ 功放      │ │ 圆形屏    │ │ 测距      │
   └───────────┘ └─────┬─────┘ └───────────┘ └───────────┘
                       │                       
                 ┌─────▼─────┐               ┌───────────┐
                 │ 腔体喇叭  │               │ WS2812B   │
                 │ 4Ω 3W    │               │ RGB 灯带  │
                 └───────────┘               └───────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         电源系统                                     │
│  18650 电池 ──▶ TP4056 充电 ──▶ MT3608 升压 5V ──▶ 各模块供电       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      可选扩展模块                                    │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐           │
│  │ OV2640    │ │ DHT22     │ │ BH1750    │ │ MPU6050   │           │
│  │ 摄像头    │ │ 温湿度    │ │ 光线      │ │ 姿态      │           │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向（语音唤醒模式）

```
┌─────────────────────────────────────────────────────────────────────┐
│  【待机监听状态】功耗 ~25mA                                          │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                      │
│  │ INMP441  │───▶│ WakeNet  │    │ 闲置动画 │  眼睛随机看看四周    │
│  │ 麦克风   │    │ 唤醒检测 │    │ 屏幕显示 │  偶尔眨眼、打哈欠    │
│  └──────────┘    └────┬─────┘    └──────────┘                      │
│                       │                                             │
│                       │ 检测到唤醒词 "Hi Wallace"                   │
│                       ▼                                             │
├─────────────────────────────────────────────────────────────────────┤
│  【唤醒状态】                                                        │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  1. RGB 灯带亮起渐变光环                                      │  │
│  │  2. 屏幕显示"聆听"表情（眼睛睁大、瞳孔放大）                  │  │
│  │  3. WiFi 快速连接 PC 服务端                                   │  │
│  │  4. CPU 提升至 240MHz                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                       │                                             │
│                       ▼                                             │
├─────────────────────────────────────────────────────────────────────┤
│  【录音上传】                                                        │
│                                                                     │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐           │
│  │ 麦克风   │ ──I2S──▶│ 音频缓存 │ ──WS───▶│ PC服务端 │           │
│  │ 采集     │         │ Opus压缩 │         │ 接收     │           │
│  └──────────┘         └──────────┘         └──────────┘           │
│                                                                     │
│  屏幕显示：眼睛专注看着用户，RGB 灯带呼吸闪烁                        │
│                       │                                             │
│                       ▼                                             │
├─────────────────────────────────────────────────────────────────────┤
│  【PC 端处理】                                                       │
│                                                                     │
│  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐  │
│  │ VAD    │──▶│ ASR    │──▶│ 记忆   │──▶│ LLM    │──▶│ TTS    │  │
│  │ 静音检测│   │ 语音识别│   │ 注入   │   │ 生成回复│   │ 语音合成│  │
│  │Silero  │   │Whisper │   │ Context│   │DeepSeek│   │Edge-TTS│  │
│  └────────┘   └────────┘   └────────┘   └───┬────┘   └────────┘  │
│                                             │                      │
│                              提取情绪标签 [mood:happy]              │
│                       │                                             │
│                       ▼                                             │
├─────────────────────────────────────────────────────────────────────┤
│  【回复播放】                                                        │
│                                                                     │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐           │
│  │ PC推送   │ ──WS───▶│ ESP32    │ ──I2S──▶│ 喇叭播放 │           │
│  │ 音频流   │         │ 缓存解码 │         │          │           │
│  └──────────┘         └──────────┘         └──────────┘           │
│                                                                     │
│  屏幕显示：根据情绪标签切换表情 + 说话时嘴巴/波形律动                │
│  RGB 灯带：随音频振幅律动                                           │
│                       │                                             │
│                       ▼                                             │
├─────────────────────────────────────────────────────────────────────┤
│  【返回待机】                                                        │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  1. 断开 WiFi，CPU 降频至 80MHz                               │  │
│  │  2. 屏幕切换回闲置动画                                        │  │
│  │  3. RGB 灯带恢复淡蓝色呼吸                                    │  │
│  │  4. 继续监听唤醒词                                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 硬件设计与引脚规划

### 3.1 核心模块引脚

#### 音频输入（INMP441 - I2S_NUM_0）

| INMP441 引脚 | ESP32-S3 GPIO | 说明 |
|-------------|---------------|------|
| SCK (BCLK)  | GPIO 41       | I2S 位时钟 |
| WS (LRC)    | GPIO 42       | I2S 字选择 |
| SD (DOUT)   | GPIO 2        | I2S 数据输出 |
| VDD         | 3.3V          | 供电 |
| GND         | GND           | 接地 |
| L/R         | GND           | 接地 = 左声道 |

#### 音频输出（MAX98357A - I2S_NUM_1）

| MAX98357A 引脚 | ESP32-S3 GPIO | 说明 |
|---------------|---------------|------|
| BCLK          | GPIO 15       | I2S 位时钟 |
| LRC           | GPIO 16       | I2S 字选择 |
| DIN           | GPIO 17       | I2S 数据输入 |
| Vin           | **5V**        | 供电 |
| GND           | GND           | 接地 |

#### 视觉显示（GC9A01 - SPI）

| GC9A01 引脚 | ESP32-S3 GPIO | 说明 |
|------------|---------------|------|
| SCL (SCK)  | GPIO 12       | SPI 时钟 |
| SDA (MOSI) | GPIO 11       | SPI 数据 |
| RES (RST)  | GPIO 10       | 复位 |
| DC         | GPIO 9        | 数据/命令 |
| CS         | GPIO 46       | 片选 |
| BLK        | GPIO 45       | 背光 PWM |
| VCC/GND    | 3.3V / GND    | 供电 |

#### RGB 灯带（WS2812B）

| WS2812B | ESP32-S3 GPIO | 说明 |
|---------|---------------|------|
| DIN     | GPIO 48       | 数据输入（支持 RMT） |
| VCC     | 5V            | 供电 |
| GND     | GND           | 接地 |

### 3.2 扩展模块引脚

#### I2C 总线（传感器共用）

| 功能 | ESP32-S3 GPIO |
|------|---------------|
| SDA  | GPIO 6        |
| SCL  | GPIO 7        |

#### 扩展模块地址

| 模块 | I2C 地址 | 功能 |
|------|---------|------|
| VL53L0X | 0x29 | 激光测距（眼神追踪） |
| BH1750 | 0x23 | 光线感应 |
| DHT22 | GPIO 4（单总线） | 温湿度 |
| MPU6050 | 0x68 | 姿态检测（摇一摇） |

#### 摄像头（OV2640，可选）

| OV2640 引脚 | ESP32-S3 GPIO |
|------------|---------------|
| SIOD (SDA) | GPIO 6        |
| SIOC (SCL) | GPIO 7        |
| VSYNC      | GPIO 38       |
| HREF       | GPIO 39       |
| PCLK       | GPIO 40       |
| D0-D7      | GPIO 18-21, 36-37, 47, 3 |
| XCLK       | GPIO 8        |

#### 其他

| 模块 | ESP32-S3 GPIO | 说明 |
|------|---------------|------|
| TTP223 触摸 | GPIO 1 (RTC) | 备用手动唤醒 |
| 物理按钮 | GPIO 0 | 彩蛋触发 |

---

## 4. 软件实现路线

### 4.1 固件端（ESP32-S3）

**开发环境**：VS Code + PlatformIO（推荐使用 ESP-IDF 5.x 工具链，官方支持 ESP-SR）

**PlatformIO 集成要点**：

1. **使用 ESP-IDF 框架**：创建 `platform = espressif32` 且 `framework = espidf` 的项目，避免与 Arduino 框架混用。
2. **版本锁定**：固定 ESP-IDF 到 5.x（与 ESP-SR/ESP-ADF 兼容），避免自动升级造成依赖破坏。
3. **组件管理**：将 ESP-SR、ESP-ADF 作为外部组件引入（`components/` 或 `extra_components_dirs`），保持与 ESP-IDF 版本匹配。
4. **PSRAM 配置**：在 `sdkconfig` 中启用 PSRAM（N16R8 必需），并设置到 8MB。
5. **分区表**：为语音模型与音频缓存预留足够 Flash 分区（建议自定义分区表）。
6. **编译优化**：开启 `Release` 构建，必要时针对 WakeNet/MultiNet 启用 `-O2` 优化。
7. **串口与监视**：在 PlatformIO 中固定串口与波特率，便于日志与性能分析。

**PlatformIO 配置示例**：

```ini
; platformio.ini
[env:esp32s3]
platform = espressif32
board = esp32-s3-devkitc-1
framework = espidf

; 锁定 ESP-IDF 版本（与 ESP-SR/ESP-ADF 兼容）
platform_packages = 
    framework-espidf @ ~5.1.0

; PSRAM 配置（N16R8 必需）
board_build.arduino.memory_type = qio_opi
board_build.psram_mode = opi

; 串口配置
monitor_speed = 115200
upload_speed = 921600

; 额外组件路径（ESP-SR、ESP-ADF 等）
board_build.cmake_extra_args = 
    -DEXTRA_COMPONENT_DIRS=${PROJECT_DIR}/components

; 分区表（为语音模型预留空间）
board_build.partitions = partitions_custom.csv
```

**自定义分区表示例** (`partitions_custom.csv`)：

```csv
# Name,   Type, SubType, Offset,   Size,    Flags
nvs,      data, nvs,     0x9000,   0x6000,
phy_init, data, phy,     0xf000,   0x1000,
factory,  app,  factory, 0x10000,  0x300000,
model,    data, spiffs,  0x310000, 0x0F0000,
```

**核心框架/库**：

| 功能 | 方案 | 说明 |
|------|------|------|
| 屏幕驱动 | LovyanGFX | Sprite 局部刷新，高帧率 |
| 音频框架 | ESP-ADF | I2S + 编解码 + 音频流水线 |
| 语音唤醒 | ESP-SR WakeNet / TFLite Micro | 本地唤醒词检测（见 4.2 节方案选择） |
| 指令识别 | ESP-SR MultiNet | 本地简单指令识别 |
| RGB 灯带 | FastLED / ESP-IDF RMT | WS2812B 驱动 |
| 传感器 | 各模块官方库 | I2C 读取 |
| 网络通信 | WebSocket + MQTT | 服务端通信 + 智能家居 |

**固件架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                      主任务调度                              │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ 音频任务 │ │ 显示任务 │ │ 传感任务 │ │ 网络任务 │           │
│  │ Core 0  │ │ Core 1  │ │ Core 0  │ │ Core 1  │           │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
│       │          │          │          │                   │
│       ▼          ▼          ▼          ▼                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   事件队列                           │   │
│  │  WAKE_WORD_DETECTED | USER_PROXIMITY | IDLE_TIMEOUT │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                 │
│                          ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   状态机                             │   │
│  │  IDLE → LISTENING → PROCESSING → SPEAKING → IDLE   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 语音唤醒方案

**推荐：开源自定义唤醒词方案（不依赖厂商付费定制）**

#### 可选实现路径

| 方案 | 检测位置 | 延迟 | 准确率 | 复杂度 | 推荐场景 |
|------|---------|------|-------|-------|---------|
| A. ESP32 本地 KWS | 设备端 | <50ms | 中等 | 中 | 追求低延迟 |
| B. PC 端唤醒 | 服务端 | 100-300ms | 高 | 低 | 追求高准确率 |
| C. 混合策略 | 设备+服务端 | <100ms | 高 | 高 | 平衡方案（推荐）|

**方案 A：ESP32 本地 KWS**

使用 TensorFlow Lite Micro / ESP-DSP 训练小型关键词模型（如 DS-CNN），模型随固件发布。

**方案 B：PC 端唤醒**

用开源 KWS 在 PC 侧检测唤醒词，再通知 ESP32 进入录音模式。

**方案 C：混合策略（推荐）**

ESP32 先做轻量预检，立即开始录音，同时 PC 端二次确认，兼顾速度与准确率。

#### 推荐开源工具链

| 工具 | 平台 | 特点 | 链接 |
|------|------|------|------|
| **openWakeWord** | PC (Python) | 准确率高、支持自定义词训练、活跃维护 | https://github.com/dscripka/openWakeWord |
| **microWakeWord** | ESP32 | 专为 ESP32 优化、ESPHome 集成、训练教程完善 | https://github.com/kahrendt/microWakeWord |
| **Porcupine** | 跨平台 | 商业级准确率、有免费 tier、支持嵌入式 | https://picovoice.ai/platform/porcupine/ |
| **Mycroft Precise** | PC (Python) | 开源、Mozilla 支持、可自训练 | https://github.com/MycroftAI/mycroft-precise |

#### 混合策略时序优化

```
┌─────────────────────────────────────────────────────────────────┐
│  【传统串行方案】延迟 = 预检 + 网络 + 确认 ≈ 200-400ms          │
│                                                                 │
│  用户说唤醒词 ──▶ ESP32预检 ──▶ 上传PC ──▶ PC确认 ──▶ 开始录音  │
│                    50ms         100ms      50ms                 │
├─────────────────────────────────────────────────────────────────┤
│  【优化并行方案】延迟 ≈ 50-100ms（推荐）                         │
│                                                                 │
│  用户说唤醒词 ──▶ ESP32预检 ──┬──▶ 立即开始录音（乐观执行）     │
│                    50ms       │                                 │
│                               └──▶ 同时上传PC确认               │
│                                         │                       │
│                               ┌─────────┴─────────┐             │
│                               ▼                   ▼             │
│                          PC确认通过          PC确认失败          │
│                          继续录音            丢弃已录内容        │
└─────────────────────────────────────────────────────────────────┘
```

> **注意**：混合策略的「乐观执行」会在误触发时浪费少量录音资源，但换来更快的响应体验。根据实测，误触发率通常 <5%，可接受。

#### 代码实现示例

```c
// wake_word_detection.h

// ============================================================
// 方案 A：使用 ESP-SR WakeNet（乐鑫官方框架）
// 优点：官方支持、文档完善
// 缺点：自定义唤醒词需适配其模型格式
// ============================================================
#ifdef USE_ESP_SR_WAKENET
#include "esp_wn_iface.h"
#include "esp_wn_models.h"

static esp_wn_iface_t *wakenet = NULL;

void init_wakenet() {
    // 加载自定义训练的模型（需转换为 WakeNet 格式）
    wakenet = esp_wn_handle_from_name("wn9_custom");
    // 或使用官方免费词："wn9_hilexin"（Hi 乐鑫）
}

bool detect_wake_word(int16_t *audio_buffer, int len) {
    int result = wakenet->detect(wakenet, audio_buffer);
    return result > 0;
}
#endif

// ============================================================
// 方案 B：使用 TensorFlow Lite Micro（完全开源）
// 优点：完全开源、自由训练、社区活跃
// 缺点：需要自行训练模型、内存占用稍大
// ============================================================
#ifdef USE_TFLITE_MICRO
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"

// 模型数据（从训练好的 .tflite 文件转换）
extern const unsigned char wake_word_model[];
extern const unsigned int wake_word_model_len;

static tflite::MicroInterpreter *interpreter = nullptr;

void init_tflite_kws() {
    // 初始化 TFLite Micro 解释器
    static tflite::MicroMutableOpResolver<10> resolver;
    resolver.AddConv2D();
    resolver.AddDepthwiseConv2D();
    resolver.AddFullyConnected();
    resolver.AddSoftmax();
    // ... 添加其他需要的算子
    
    static tflite::MicroInterpreter static_interpreter(
        model, resolver, tensor_arena, kTensorArenaSize);
    interpreter = &static_interpreter;
    interpreter->AllocateTensors();
}

bool detect_wake_word(int16_t *audio_buffer, int len) {
    // 预处理：提取 MFCC 特征
    extract_mfcc_features(audio_buffer, len, interpreter->input(0)->data.f);
    
    // 推理
    interpreter->Invoke();
    
    // 获取结果
    float *output = interpreter->output(0)->data.f;
    return output[1] > 0.8f;  // 唤醒词类别置信度 > 0.8
}
#endif

// ============================================================
// 混合策略：ESP32 预检 + PC 确认（并行执行）
// ============================================================
void on_local_wake_detected() {
    // 1. 立即开始录音（乐观执行）
    start_recording_optimistic();
    
    // 2. 同时发送预检结果给 PC 确认
    send_wake_event_to_pc(audio_snippet, SNIPPET_LEN);
}

void on_pc_confirmation(bool confirmed) {
    if (confirmed) {
        // PC 确认通过，继续正常流程
        continue_recording();
    } else {
        // PC 确认失败（误触发），丢弃已录内容
        discard_recording();
        return_to_idle();
    }
}
```

#### 本地指令识别（无需联网）

```c
// local_commands.h
#include "esp_mn_iface.h"

// 定义本地指令（MultiNet 识别）
const char *local_commands[] = {
    "打开灯",      // ID: 0
    "关闭灯",      // ID: 1
    "调亮一点",    // ID: 2
    "调暗一点",    // ID: 3
    "播放音乐",    // ID: 4
    "暂停",        // ID: 5
    "现在几点",    // ID: 6
    "今天星期几",  // ID: 7
    "设置闹钟",    // ID: 8
    "取消闹钟",    // ID: 9
};
```

#### 唤醒流程

```
持续监听 ──▶ 唤醒词检测 ──▶ 检测到唤醒词
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
          后续是简单指令？              后续是复杂问题？
                 │                           │
                 ▼                           ▼
          MultiNet本地识别             上传PC服务端
          直接执行动作                 LLM处理回复
          （延迟 <100ms）              （延迟 ~1-3s）
```

### 4.3 服务端（PC）

**技术栈**：Python 3.10+ / FastAPI / WebSocket / MQTT

**核心处理流程**：

```python
# server.py
from fastapi import FastAPI, WebSocket
from langchain_ollama import ChatOllama
from langchain.memory import ConversationBufferWindowMemory
import faster_whisper
import edge_tts
import json

app = FastAPI()

# 用户记忆存储
user_memories = {}

# 初始化模型
whisper = faster_whisper.WhisperModel("large-v3-turbo")
llm = ChatOllama(model="deepseek-r1:8b")

def get_user_context(user_id: str) -> str:
    """获取用户记忆上下文"""
    memory = user_memories.get(user_id, {})
    return f"""
    用户名：{memory.get('name', '朋友')}
    偏好：{memory.get('preferences', [])}
    最近话题：{memory.get('recent_topics', [])}
    """

def extract_mood(response: str) -> str:
    """从回复中提取情绪标签"""
    # 简单规则 or 让LLM自己标注
    if any(word in response for word in ['哈哈', '太好了', '开心']):
        return 'happy'
    elif any(word in response for word in ['抱歉', '遗憾', '难过']):
        return 'sad'
    elif any(word in response for word in ['嗯...', '让我想想', '这个问题']):
        return 'thinking'
    return 'neutral'

@app.websocket("/ws/{user_id}")
async def chat(websocket: WebSocket, user_id: str):
    await websocket.accept()
    
    while True:
        # 1. 接收音频
        audio_data = await websocket.receive_bytes()
        
        # 2. ASR
        segments, _ = whisper.transcribe(audio_data)
        text = "".join([s.text for s in segments])
        
        # 3. 注入记忆上下文
        context = get_user_context(user_id)
        prompt = f"{context}\n\n用户说：{text}"
        
        # 4. LLM 生成
        response = llm.invoke(prompt)
        reply = response.content
        
        # 5. 提取情绪
        mood = extract_mood(reply)
        
        # 6. 发送情绪标签
        await websocket.send_json({"type": "mood", "mood": mood})
        
        # 7. TTS 流式推送
        communicate = edge_tts.Communicate(reply, voice="zh-CN-XiaoxiaoNeural")
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                await websocket.send_bytes(chunk["data"])
        
        # 8. 更新记忆
        update_memory(user_id, text, reply)
```

---

## 5. 拟人化体验设计

### 5.1 情绪系统

**情绪状态定义**：

| 情绪 | 触发条件 | 眼睛表现 | RGB 灯带 |
|------|---------|---------|---------|
| 😊 开心 | 正面回复、夸奖 | 弯成月牙，瞳孔放大 | 暖黄色快速呼吸 |
| 😢 难过 | 负面话题、道歉 | 下垂，泪滴动画 | 蓝色缓慢呼吸 |
| 🤔 思考 | 复杂问题、等待 | 向上看，瞳孔转圈 | 紫色流水 |
| 😠 生气 | 被骂、不满 | 眉毛下压，瞳孔缩小 | 红色闪烁 |
| 😴 困了 | 长时间空闲 | 慢慢眯起，打哈欠 | 暗淡橙色 |
| 😲 惊讶 | 意外信息 | 睁大，瞳孔放大 | 白色闪烁 |
| 😏 傲娇 | 特定性格模式 | 斜眼，微微上扬 | 粉色 |

**实现代码示例**：

```cpp
// emotions.h
enum Emotion {
    HAPPY, SAD, THINKING, ANGRY, SLEEPY, SURPRISED, TSUNDERE, NEUTRAL
};

struct EmotionState {
    Emotion current;
    uint8_t intensity;  // 0-100 强度
    uint32_t duration;  // 持续时间
};

// 眼睛绘制
void drawEmotion(Emotion emotion) {
    switch (emotion) {
        case HAPPY:
            // 弯月牙眼睛
            sprite.fillCircle(120, 120, 80, TFT_WHITE);
            sprite.fillArc(120, 100, 60, 70, 200, 340, TFT_BLACK);
            break;
            
        case SAD:
            // 下垂眼睛 + 泪滴
            sprite.fillCircle(120, 130, 70, TFT_WHITE);
            sprite.fillCircle(120, 140, 30, TFT_BLACK);
            sprite.fillCircle(90, 160, 8, TFT_CYAN);  // 泪滴
            break;
            
        case THINKING:
            // 眼睛向上看
            sprite.fillCircle(120, 120, 80, TFT_WHITE);
            sprite.fillCircle(120, 90, 35, TFT_BLACK);  // 瞳孔上移
            break;
            
        // ... 其他情绪
    }
    sprite.pushSprite(0, 0);
}
```

### 5.2 眼神追踪

**使用 VL53L0X 激光测距传感器检测用户方位**：

```cpp
// eye_tracking.h
#include <VL53L0X.h>

VL53L0X distanceSensor;

struct UserPosition {
    int distance;      // 距离 mm
    int direction;     // 方向（需要多个传感器或摄像头）
    bool isPresent;    // 是否有人
};

void updateEyeTracking() {
    int distance = distanceSensor.readRangeSingleMillimeters();
    
    if (distance < 500) {
        // 用户很近，瞳孔放大表示关注
        pupilSize = 40;
        pupilY = 120;  // 直视
    } else if (distance < 1500) {
        // 正常距离
        pupilSize = 30;
    } else {
        // 用户较远或离开
        pupilSize = 25;
        // 眼睛可以"失落"地低下
        pupilY = 140;
    }
}

// 如果有多个测距传感器，可以判断左右
void trackUserDirection(int leftDist, int rightDist) {
    if (leftDist < rightDist - 100) {
        pupilX = 90;   // 看向左边
    } else if (rightDist < leftDist - 100) {
        pupilX = 150;  // 看向右边
    } else {
        pupilX = 120;  // 看正前方
    }
}
```

### 5.3 闲置动画

**让 Wallace 在无交互时也"活着"**：

```cpp
// idle_animations.h

enum IdleAction {
    LOOK_AROUND,      // 随机看看四周
    BLINK,            // 眨眼
    YAWN,             // 打哈欠
    CURIOUS_LOOK,     // 好奇地盯着某处
    SLIGHT_MOVEMENT,  // 轻微晃动
    HUM_TUNE,         // 哼小曲（播放音效）
};

void playIdleAnimation() {
    static uint32_t lastAction = 0;
    static uint32_t nextActionDelay = 3000;
    
    if (millis() - lastAction > nextActionDelay) {
        // 随机选择一个动作
        IdleAction action = (IdleAction)random(0, 6);
        
        switch (action) {
            case LOOK_AROUND:
                // 眼睛随机看向某个方向，3秒后回正
                pupilX = random(80, 160);
                pupilY = random(90, 150);
                delay(2000);
                pupilX = 120;
                pupilY = 120;
                break;
                
            case BLINK:
                // 快速眨眼
                for (int i = 0; i < 2; i++) {
                    drawBlinkFrame(true);
                    delay(80);
                    drawBlinkFrame(false);
                    delay(80);
                }
                break;
                
            case YAWN:
                // 打哈欠动画
                playYawnAnimation();
                break;
                
            case HUM_TUNE:
                // 10% 概率哼小曲
                if (random(100) < 10) {
                    playRandomTune();
                }
                break;
        }
        
        lastAction = millis();
        nextActionDelay = random(3000, 10000);  // 3-10秒随机间隔
    }
}
```

### 5.4 呼吸灯效果

**WS2812B RGB 灯带状态反馈**：

```cpp
// led_effects.h
#include <FastLED.h>

#define NUM_LEDS 12
#define LED_PIN 48

CRGB leds[NUM_LEDS];

enum LedEffect {
    BREATHING,        // 呼吸
    RAINBOW_CHASE,    // 彩虹追逐
    PULSE,            // 脉冲
    AUDIO_REACTIVE,   // 音频响应
    ALERT,            // 警告闪烁
};

// 状态对应的灯效
void setLedState(SystemState state) {
    switch (state) {
        case STATE_IDLE:
            // 淡蓝色缓慢呼吸
            breathingEffect(CRGB::DodgerBlue, 3000);
            break;
            
        case STATE_LISTENING:
            // 亮起渐变光环
            rainbowChase(50);
            break;
            
        case STATE_THINKING:
            // 紫色流水追逐
            chaseEffect(CRGB::Purple, 100);
            break;
            
        case STATE_SPEAKING:
            // 随音频振幅律动
            audioReactiveEffect();
            break;
            
        case STATE_LOW_BATTERY:
            // 红色闪烁警告
            blinkEffect(CRGB::Red, 500);
            break;
    }
}

// 音频响应效果
void audioReactiveEffect() {
    // 从音频缓冲区计算振幅
    int amplitude = getAudioAmplitude();
    int brightness = map(amplitude, 0, 4096, 50, 255);
    
    for (int i = 0; i < NUM_LEDS; i++) {
        leds[i] = CHSV(160, 255, brightness);  // 蓝绿色
    }
    FastLED.show();
}
```

---

## 6. AI 能力扩展

### 6.1 记忆系统

**让 Wallace 记住用户**：

```python
# memory_system.py
import json
from datetime import datetime
from pathlib import Path

class UserMemory:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.file_path = Path(f"memories/{user_id}.json")
        self.load()
    
    def load(self):
        if self.file_path.exists():
            with open(self.file_path) as f:
                self.data = json.load(f)
        else:
            self.data = {
                "name": None,
                "preferences": [],
                "interests": [],
                "recent_topics": [],
                "important_dates": {},
                "interaction_count": 0,
                "first_met": datetime.now().isoformat(),
            }
    
    def save(self):
        self.file_path.parent.mkdir(exist_ok=True)
        with open(self.file_path, 'w') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def update_from_conversation(self, user_text: str, ai_response: str):
        """从对话中提取并更新记忆"""
        self.data["interaction_count"] += 1
        
        # 提取用户名
        if "我叫" in user_text or "我是" in user_text:
            # 简单提取，实际可用NER
            name = extract_name(user_text)
            if name:
                self.data["name"] = name
        
        # 提取偏好
        if "喜欢" in user_text:
            preference = extract_preference(user_text)
            if preference and preference not in self.data["preferences"]:
                self.data["preferences"].append(preference)
        
        # 更新最近话题（保留最近5个）
        topic = summarize_topic(user_text)
        self.data["recent_topics"].insert(0, {
            "topic": topic,
            "time": datetime.now().isoformat()
        })
        self.data["recent_topics"] = self.data["recent_topics"][:5]
        
        self.save()
    
    def get_context_prompt(self) -> str:
        """生成记忆上下文提示词"""
        name = self.data.get("name") or "朋友"
        prefs = ", ".join(self.data.get("preferences", [])) or "暂未了解"
        
        recent = ""
        if self.data.get("recent_topics"):
            recent = f"上次聊了：{self.data['recent_topics'][0]['topic']}"
        
        return f"""
你正在和{name}对话。
你了解到ta的偏好：{prefs}
{recent}
请根据这些信息，用亲切自然的语气回复。
"""
```

**效果示例**：

```
第一次对话：
用户："你好，我叫小明"
Wallace："你好小明！很高兴认识你～有什么我可以帮你的吗？"

一周后：
用户："早上好"
Wallace："早上好小明！记得你说过早起困难，今天起得挺早啊，是有什么重要的事吗？"
```

### 6.2 主动关怀

**定时任务 + 事件触发**：

```python
# proactive_care.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx

scheduler = AsyncIOScheduler()

# 定时提醒
@scheduler.scheduled_job('interval', hours=2)
async def sedentary_reminder():
    """久坐提醒"""
    await send_to_device("已经坐了两个小时了，要不要站起来活动一下？", mood="caring")

@scheduler.scheduled_job('cron', hour=7, minute=30)
async def morning_greeting():
    """早安问候 + 天气"""
    weather = await get_weather()
    msg = f"早上好！今天{weather['description']}，气温{weather['temp']}度。"
    if weather['temp'] < 10:
        msg += "有点冷，记得多穿点哦～"
    await send_to_device(msg, mood="happy")

@scheduler.scheduled_job('cron', hour=22, minute=0)
async def night_reminder():
    """晚安提醒"""
    await send_to_device("已经十点了，今天辛苦了，早点休息吧～", mood="gentle")

# 特殊日期提醒
async def check_special_dates(user_memory):
    today = datetime.now().strftime("%m-%d")
    important_dates = user_memory.data.get("important_dates", {})
    
    if today in important_dates:
        event = important_dates[today]
        if event["type"] == "birthday":
            await send_to_device(
                f"今天是你的生日！祝你生日快乐！🎂🎉", 
                mood="excited"
            )
```

### 6.3 多模态输入

**OV2640 摄像头扩展**：

```cpp
// camera_features.h
#include "esp_camera.h"
#include "human_face_detect_msr01.hpp"

// 人脸检测
void detectFace() {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) return;
    
    // 使用 ESP-WHO 人脸检测
    std::list<dl::detect::result_t> results;
    detector.infer((uint8_t *)fb->buf, {fb->height, fb->width, 3});
    results = detector.get_results();
    
    if (!results.empty()) {
        // 检测到人脸
        onFaceDetected(results.front());
    }
    
    esp_camera_fb_return(fb);
}

void onFaceDetected(dl::detect::result_t &face) {
    // 计算人脸位置，调整眼神
    int face_center_x = (face.box[0] + face.box[2]) / 2;
    
    if (face_center_x < fb->width / 3) {
        lookLeft();
    } else if (face_center_x > fb->width * 2 / 3) {
        lookRight();
    } else {
        lookCenter();
    }
}
```

### 6.4 本地指令识别

**简单指令无需联网**：

```cpp
// local_commands.h
#include "esp_mn_iface.h"

// 定义本地指令
const char *local_commands[] = {
    "打开灯",      // ID: 0
    "关闭灯",      // ID: 1
    "调亮一点",    // ID: 2
    "调暗一点",    // ID: 3
    "播放音乐",    // ID: 4
    "暂停",        // ID: 5
    "现在几点",    // ID: 6
    "今天星期几",  // ID: 7
    "设置闹钟",    // ID: 8
    "取消闹钟",    // ID: 9
};

void handleLocalCommand(int command_id) {
    switch (command_id) {
        case 0: // 打开灯
            mqtt_publish("home/light/bedroom", "ON");
            speak("好的，灯已打开");
            break;
            
        case 1: // 关闭灯
            mqtt_publish("home/light/bedroom", "OFF");
            speak("好的，灯已关闭");
            break;
            
        case 6: // 现在几点
            char timeStr[32];
            getLocalTime(&timeinfo);
            sprintf(timeStr, "现在是%d点%d分", timeinfo.tm_hour, timeinfo.tm_min);
            speak(timeStr);
            break;
            
        // ... 其他指令
    }
}
```

---

## 7. 环境感知与智能家居

### 7.1 环境传感器

| 传感器 | 型号 | 功能 | 交互示例 |
|--------|------|------|---------|
| 温湿度 | DHT22 | 环境舒适度 | "现在室内26度，湿度60%，挺舒适的" |
| 光线 | BH1750 | 光照强度 | "光线有点暗，要不要开灯？" |
| 空气质量 | MQ-135 | 有害气体 | "空气质量不太好，建议开窗通风" |
| 气压 | BMP280 | 天气变化 | "气压在下降，可能要下雨了" |

**环境监测代码**：

```cpp
// environment_monitor.h
#include <DHT.h>
#include <BH1750.h>

DHT dht(DHT_PIN, DHT22);
BH1750 lightMeter;

struct Environment {
    float temperature;
    float humidity;
    uint16_t light;
    bool isComfortable;
};

Environment readEnvironment() {
    Environment env;
    env.temperature = dht.readTemperature();
    env.humidity = dht.readHumidity();
    env.light = lightMeter.readLightLevel();
    
    // 判断舒适度
    env.isComfortable = (env.temperature >= 20 && env.temperature <= 26 &&
                         env.humidity >= 40 && env.humidity <= 60);
    
    return env;
}

// 主动提醒
void checkEnvironmentAlerts(Environment &env) {
    if (env.temperature > 28) {
        queueMessage("有点热了，要不要开空调？", MOOD_CARING);
    }
    
    if (env.humidity < 30) {
        queueMessage("空气有点干燥，记得多喝水哦", MOOD_CARING);
    }
    
    if (env.light < 100 && isEvening()) {
        queueMessage("光线有点暗了，要不要开灯？", MOOD_CURIOUS);
    }
}
```

### 7.2 智能家居联动

**MQTT 控制协议**：

```cpp
// smart_home.h
#include <PubSubClient.h>

WiFiClient espClient;
PubSubClient mqtt(espClient);

// 设备定义
struct SmartDevice {
    const char *name;
    const char *topic;
    const char *type;  // light, switch, climate, etc.
};

SmartDevice devices[] = {
    {"卧室灯", "home/light/bedroom", "light"},
    {"客厅灯", "home/light/living", "light"},
    {"空调", "home/climate/ac", "climate"},
    {"加湿器", "home/switch/humidifier", "switch"},
};

void controlDevice(const char *deviceName, const char *action) {
    for (auto &dev : devices) {
        if (strcmp(dev.name, deviceName) == 0) {
            mqtt.publish(dev.topic, action);
            return;
        }
    }
}

// 场景控制
void executeScene(const char *sceneName) {
    if (strcmp(sceneName, "睡觉") == 0) {
        controlDevice("卧室灯", "OFF");
        controlDevice("客厅灯", "OFF");
        mqtt.publish("home/climate/ac", "{\"mode\":\"sleep\"}");
        speak("好的，晚安～");
    }
    else if (strcmp(sceneName, "起床") == 0) {
        controlDevice("卧室灯", "ON");
        // 渐亮效果
        for (int i = 0; i <= 100; i += 10) {
            char brightness[16];
            sprintf(brightness, "{\"brightness\":%d}", i);
            mqtt.publish("home/light/bedroom", brightness);
            delay(500);
        }
        speak("早上好，新的一天开始了！");
    }
}
```

---

## 8. 趣味玩法

### 8.1 小游戏模式

**猜数字**：

```cpp
// games/guess_number.h
class GuessNumberGame {
    int secretNumber;
    int attempts;
    int maxAttempts = 7;
    
public:
    void start() {
        secretNumber = random(1, 101);
        attempts = 0;
        speak("我想了一个1到100之间的数字，你来猜猜看！");
        setEmotion(PLAYFUL);
    }
    
    void guess(int number) {
        attempts++;
        
        if (number == secretNumber) {
            speak(String("恭喜你猜对了！用了") + attempts + "次！");
            setEmotion(EXCITED);
            showWinAnimation();
        }
        else if (attempts >= maxAttempts) {
            speak(String("很遗憾，答案是") + secretNumber + "，下次再挑战吧！");
            setEmotion(SAD);
        }
        else if (number > secretNumber) {
            speak("大了，再猜小一点～");
            showHintAnimation(false);  // 向下箭头
        }
        else {
            speak("小了，再猜大一点～");
            showHintAnimation(true);   // 向上箭头
        }
    }
};
```

**成语接龙**：

```python
# games/idiom_chain.py
class IdiomChainGame:
    def __init__(self):
        self.idioms = load_idiom_database()
        self.used = set()
        self.last_char = None
    
    def player_turn(self, idiom: str) -> str:
        # 验证成语
        if idiom not in self.idioms:
            return "[mood:confused] 这个好像不是成语哦，换一个试试？"
        
        # 验证首字
        if self.last_char and idiom[0] != self.last_char:
            return f"[mood:playful] 要用'{self.last_char}'开头哦！"
        
        # 验证是否用过
        if idiom in self.used:
            return "[mood:thinking] 这个说过了，换一个吧！"
        
        self.used.add(idiom)
        self.last_char = idiom[-1]
        
        # AI 接龙
        ai_idiom = self.find_idiom(self.last_char)
        if ai_idiom:
            self.used.add(ai_idiom)
            self.last_char = ai_idiom[-1]
            return f"[mood:happy] {ai_idiom}！轮到你了，'{self.last_char}'开头～"
        else:
            return "[mood:surprised] 我想不出来了，你赢了！"
```

### 8.2 桌面宠物模式

**自主行为状态机**：

```cpp
// pet_mode.h
enum PetState {
    PET_IDLE,       // 发呆
    PET_CURIOUS,    // 好奇
    PET_PLAYFUL,    // 想玩
    PET_SLEEPY,     // 困了
    PET_HUNGRY,     // 饿了（需要"喂食"互动）
};

class DesktopPet {
    PetState state = PET_IDLE;
    int happiness = 50;    // 0-100
    int energy = 100;      // 0-100
    uint32_t lastInteraction = 0;
    
public:
    void update() {
        uint32_t now = millis();
        uint32_t idleTime = now - lastInteraction;
        
        // 能量随时间下降
        energy = max(0, energy - 1);
        
        // 根据能量切换状态
        if (energy < 20) {
            setState(PET_SLEEPY);
        }
        else if (idleTime > 60000 && random(100) < 5) {
            // 长时间无互动，可能会主动找你玩
            setState(PET_PLAYFUL);
            speak("陪我玩会儿嘛～");
        }
        else if (random(100) < 2) {
            // 随机好奇
            setState(PET_CURIOUS);
            lookAtRandomDirection();
        }
        
        // 显示当前状态动画
        showPetAnimation(state);
    }
    
    void interact(InteractionType type) {
        lastInteraction = millis();
        
        switch (type) {
            case INTERACT_PET:   // 摸摸头（触摸传感器）
                happiness = min(100, happiness + 10);
                showHeartAnimation();
                speak("嘿嘿～");
                break;
                
            case INTERACT_FEED:  // 喂食（说"吃东西"）
                energy = min(100, energy + 30);
                showEatingAnimation();
                speak("好吃！谢谢～");
                break;
                
            case INTERACT_PLAY:  // 玩游戏
                happiness = min(100, happiness + 20);
                energy = max(0, energy - 10);
                startMiniGame();
                break;
        }
    }
};
```

### 8.3 实用工具

**番茄钟**：

```cpp
// tools/pomodoro.h
class PomodoroTimer {
    int workMinutes = 25;
    int breakMinutes = 5;
    int sessions = 0;
    
public:
    void start() {
        speak("番茄钟开始！专注25分钟～");
        showTimerOnScreen(workMinutes * 60);
        setEmotion(FOCUSED);
        
        // 定时器回调
        esp_timer_create(&timer_args, &timer_handle);
        esp_timer_start_once(timer_handle, workMinutes * 60 * 1000000);
    }
    
    void onWorkComplete() {
        sessions++;
        speak("时间到！休息5分钟吧～");
        setEmotion(RELAXED);
        showBreakAnimation();
        
        // 每4个番茄钟长休息
        if (sessions % 4 == 0) {
            speak("已经完成4个番茄钟了，休息15分钟吧！");
        }
    }
};
```

**阅读助手**（需要摄像头）：

```python
# tools/reading_assistant.py
import pytesseract
from PIL import Image

async def read_page(image_bytes: bytes) -> str:
    """OCR 识别页面文字"""
    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image, lang='chi_sim+eng')
    return text

async def explain_word(word: str) -> str:
    """解释单词/词语"""
    prompt = f"请用简单易懂的方式解释'{word}'的意思，并给出一个例句。"
    response = await llm.ainvoke(prompt)
    return response.content
```

### 8.4 彩蛋功能

**物理按钮触发**：

```cpp
// easter_eggs.h
#include <OneButton.h>

OneButton easterButton(GPIO_NUM_0, true);

void setupEasterEggs() {
    // 连按三下：切换性格
    easterButton.attachMultiClick([]() {
        int clicks = easterButton.getNumberClicks();
        if (clicks == 3) {
            cyclePersonality();
        }
    });
    
    // 长按3秒：树洞模式
    easterButton.attachLongPressStart([]() {
        enterTreeHoleMode();
    });
}

// 性格切换
enum Personality {
    PERSONALITY_NORMAL,    // 普通
    PERSONALITY_COLD,      // 高冷
    PERSONALITY_CHATTY,    // 话痨
    PERSONALITY_TSUNDERE,  // 傲娇
};

void cyclePersonality() {
    currentPersonality = (Personality)((currentPersonality + 1) % 4);
    
    switch (currentPersonality) {
        case PERSONALITY_NORMAL:
            speak("好的，恢复正常模式～");
            break;
        case PERSONALITY_COLD:
            speak("哦。");
            break;
        case PERSONALITY_CHATTY:
            speak("太好了太好了！我最喜欢聊天了！你今天怎么样？吃了吗？最近在忙什么呀？");
            break;
        case PERSONALITY_TSUNDERE:
            speak("哼，才不是为了你才换的模式呢！");
            break;
    }
}

// 树洞模式：只听不说，不记录
void enterTreeHoleMode() {
    speak("进入树洞模式。我会安静地听你说，不会记录任何内容。");
    setEmotion(GENTLE);
    disableMemory();
    disableCloudUpload();
}
```

**摇一摇**（需要 MPU6050）：

```cpp
// 检测摇晃
void checkShake() {
    int16_t ax, ay, az;
    mpu.getAcceleration(&ax, &ay, &az);
    
    float magnitude = sqrt(ax*ax + ay*ay + az*az);
    
    if (magnitude > SHAKE_THRESHOLD) {
        // 随机冷知识
        String fact = getRandomFact();
        speak("你知道吗？" + fact);
        setEmotion(SURPRISED);
    }
}
```

---

## 9. 电源管理策略

### 9.1 供电架构

```
18650 电池 (3.7V, 2500mAh)
    │
    ▼
TP4056 充电保护模块 (Type-C)
    │
    ├──▶ MT3608 升压 ──▶ 5V
    │         │
    │         ├──▶ MAX98357A 功放
    │         ├──▶ WS2812B RGB 灯带
    │         └──▶ ESP32-S3 (5V Pin)
    │                   │
    │                   └──▶ 板载 LDO ──▶ 3.3V
    │                                       │
    │                                       ├──▶ INMP441 麦克风
    │                                       ├──▶ GC9A01 屏幕
    │                                       └──▶ I2C 传感器
    │
    └──▶ 电池电压检测 (ADC)
              │
              └──▶ 低电量警告 (<3.3V)
```

### 9.2 功耗预估与续航

| 工作状态 | 功耗 | 说明 |
|---------|------|------|
| 语音唤醒待机 | ~25mA | 麦克风 + WakeNet + 闲置动画 |
| 唤醒后录音 | ~80mA | + WiFi 连接 |
| 播放回复 | ~150mA | + 功放全功率 + 屏幕最亮 |
| 全功能运行 | ~200mA | + RGB 灯带 + 传感器 |
| 深度睡眠 | ~10μA | 仅 RTC + 触摸唤醒 |

**续航估算（2500mAh 电池）**：

| 使用模式 | 预估续航 |
|---------|---------|
| 纯语音唤醒待机（闲置动画开） | 约 80 小时（3.3 天） |
| 每天 50 次对话（每次 30 秒） | 约 3 天 |
| 深度睡眠 + 触摸唤醒 | 数月 |
| 全功能持续运行 | 约 12 小时 |

### 9.3 低功耗优化策略

**分级功耗管理**：

```cpp
// power_management.h
enum PowerMode {
    POWER_FULL,       // 全功能
    POWER_NORMAL,     // 正常（关闭部分传感器）
    POWER_SAVING,     // 省电（关闭灯带、降低屏幕亮度）
    POWER_ULTRA_LOW,  // 超低功耗（关闭屏幕、只保留唤醒）
    POWER_SLEEP,      // 深度睡眠
};

void setPowerMode(PowerMode mode) {
    switch (mode) {
        case POWER_FULL:
            setCpuFrequencyMhz(240);
            enableAllSensors();
            setScreenBrightness(255);
            enableRgbLed();
            break;
            
        case POWER_NORMAL:
            setCpuFrequencyMhz(160);
            disableCamera();
            setScreenBrightness(200);
            break;
            
        case POWER_SAVING:
            setCpuFrequencyMhz(80);
            disableRgbLed();
            setScreenBrightness(100);
            disableAllSensorsExceptMic();
            break;
            
        case POWER_ULTRA_LOW:
            setCpuFrequencyMhz(80);
            disableScreen();
            disableRgbLed();
            disableAllSensorsExceptMic();
            break;
            
        case POWER_SLEEP:
            esp_sleep_enable_ext0_wakeup(GPIO_NUM_1, HIGH);
            esp_deep_sleep_start();
            break;
    }
}

// 自动切换策略
void autoPowerManagement() {
    float batteryVoltage = readBatteryVoltage();
    uint32_t idleTime = getIdleTime();
    
    if (batteryVoltage < 3.3) {
        // 低电量警告
        speak("电量不足，请充电");
        setPowerMode(POWER_ULTRA_LOW);
    }
    else if (idleTime > 30 * 60 * 1000) {
        // 30分钟无交互
        setPowerMode(POWER_SLEEP);
    }
    else if (idleTime > 5 * 60 * 1000) {
        // 5分钟无交互
        setPowerMode(POWER_SAVING);
    }
}
```

---

## 10. 硬件采购清单（BOM）

### 10.1 核心模块（必选）

| 类别 | 名称 | 规格 | 数量 | 参考价 | 备注 |
|------|------|------|------|-------|------|
| 主控 | ESP32-S3 开发板 | N16R8，Type-C，双 USB | 2 | ¥35-50 | ⚠️ 检查 5V 引脚 |
| 显示 | GC9A01 圆形屏 | 1.28寸，SPI，带底板 | 1 | ¥15-25 | 必须带底板 |
| 音频输入 | INMP441 麦克风 | I2S 数字麦克风 | 2 | ¥8-12 | - |
| 音频输出 | MAX98357A 功放 | I2S，3W D类 | 2 | ¥6-10 | 需 5V 供电 |
| 发声 | 腔体喇叭 | 4Ω 3W，带音腔 | 1 | ¥5-10 | 必须带音腔 |
| 电池 | 18650 电池+盒 | 2500mAh+ | 1组 | ¥15-25 | - |
| 充电 | TP4056 模块 | Type-C，带保护 | 2 | ¥3-5 | - |
| 升压 | MT3608 模块 | DC-DC 2A | 2 | ¥2-4 | 调至 5V |
| 灯效 | WS2812B 灯带 | 12颗/环形 | 1 | ¥5-10 | 状态反馈 |
| 交互 | TTP223 触摸 | 电容式 | 2 | ¥1-2 | 备用唤醒 |
| 开关 | 拨动开关 | SS12D00 | 5 | ¥0.5 | 总电源 |
| 连接 | 杜邦线+排针 | 10cm，各种 | 1批 | ¥10 | 尽量短 |
| 滤波 | 电解电容 | 100μF 16V | 5 | ¥1 | 升压滤波 |

**核心模块总计**：约 ¥150-200

### 10.2 扩展模块（可选）

| 优先级 | 名称 | 规格 | 数量 | 参考价 | 功能 |
|--------|------|------|------|-------|------|
| ⭐⭐⭐⭐⭐ | VL53L0X | 激光测距 I2C | 1 | ¥8-12 | 眼神追踪 |
| ⭐⭐⭐⭐ | DHT22 | 温湿度传感器 | 1 | ¥8-12 | 环境感知 |
| ⭐⭐⭐⭐ | BH1750 | 光线传感器 I2C | 1 | ¥3-5 | 光线感知 |
| ⭐⭐⭐ | MPU6050 | 六轴姿态 I2C | 1 | ¥5-8 | 摇一摇彩蛋 |
| ⭐⭐⭐ | 物理按钮 | 轻触按键 | 2 | ¥0.5 | 彩蛋触发 |
| ⭐⭐ | OV2640 | 摄像头模块 | 1 | ¥15-20 | 人脸检测 |
| ⭐⭐ | MQ-135 | 空气质量 | 1 | ¥8-12 | 空气监测 |
| ⭐ | SD卡模块 | SPI 接口 | 1 | ¥3-5 | 本地存储 |

**扩展模块总计**：约 ¥50-80（全选）

### 10.3 采购注意事项

#### ⚠️ ESP32-S3 开发板 5V 引脚问题

**问题**：中国版 ESP32-S3 N16R8 开发板 5V 引脚默认只有 ~1.8V。

**解决**：
1. 焊接短接板背面的 **IN-OUT 焊盘**
2. 或直接从 MT3608 输出 5V 给功放（推荐）

#### 其他注意事项

1. **ESP32-S3 必须是 N16R8**：8MB PSRAM 是跑唤醒词模型的硬性要求
2. **屏幕必须带 PCB 底板**：裸屏极难焊接
3. **喇叭必须带音腔**：否则音质很差
4. **杜邦线尽量短**：I2S 信号超过 10cm 可能有杂音
5. **RGB 灯带选环形**：方便安装在底座
6. **VL53L0X 安装位置**：需要正对用户方向

---

## 11. 已知问题与解决方案

### 11.1 I2S 驱动冲突

**问题**：同时使用麦克风和功放可能冲突。

**解决**：
- 使用 ESP-ADF 统一管理
- 麦克风用 I2S_NUM_0，功放用 I2S_NUM_1
- 不要混用新旧版 I2S 驱动

### 11.2 升压模块噪音

**问题**：MT3608 可能导致喇叭底噪。

**解决**：
- 输出端加 100μF 电解电容
- 升压模块远离麦克风
- I2S 线尽量短

### 11.3 唤醒词误触发

**问题**：电视等环境音误触发。

**解决**：
- 选择独特的唤醒词
- 调整检测阈值
- 增加二次确认逻辑

### 11.4 WiFi 重连延迟

**问题**：唤醒后 WiFi 连接慢。

**解决**：
- 使用静态 IP
- 保存 WiFi 信道信息
- 考虑使用 ESP-NOW 替代部分场景

---

## 12. 硬件形态创意

### 12.1 模块化设计

```
┌─────────────────┐
│   眼睛模块      │  ← 可更换不同风格外壳
│  (屏幕+主板)    │
├─────────────────┤
│   身体模块      │  ← 电池+扩展传感器
│  (可拆卸)       │
├─────────────────┤
│   底座模块      │  ← 可选：充电底座/灯带底座
│  (多种选择)     │
└─────────────────┘
```

### 12.2 多形态变体

| 形态 | 特点 | 场景 |
|------|------|------|
| 桌面球 | 标准版，球形外壳 | 书桌、床头 |
| 显示器挂件 | 迷你版，夹子固定 | 电脑旁 |
| 床头灯版 | 集成夜灯功能 | 卧室 |
| 车载版 | 吸盘固定，语音导航 | 汽车 |
| 挂绳版 | 超迷你，随身携带 | 外出 |

### 12.3 外壳材质建议

| 材质 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| 3D 打印 PLA | 成本低、易定制 | 精度一般 | 原型阶段 |
| 3D 打印树脂 | 精度高、光滑 | 成本较高 | 小批量 |
| 亚克力 | 透明、质感好 | 需要切割加工 | 灯效展示 |
| 硅胶 | 手感好、可爱 | 需要开模 | 量产 |

---

## 13. 开发路线图

### Phase 1: 基础功能（2-3 周）

```
□ 硬件组装与测试
  ├── ESP32-S3 上电测试
  ├── 5V 引脚修复
  ├── 各模块单独验证
  └── 整体连线

□ 核心软件
  ├── GC9A01 屏幕驱动
  ├── INMP441 录音测试
  ├── MAX98357A 播放测试
  └── WiFi + WebSocket 通信

□ 基础交互
  ├── 语音唤醒词集成
  ├── PC 服务端搭建
  └── 端到端语音对话
```

### Phase 2: 拟人化体验（2-3 周）

```
□ 情绪系统
  ├── 情绪状态定义
  ├── 眼睛动画实现
  └── LLM 情绪标签提取

□ 视觉反馈
  ├── RGB 灯带状态效果
  ├── 闲置动画
  └── 说话波形动效

□ 眼神追踪（可选）
  ├── VL53L0X 集成
  └── 瞳孔跟随逻辑
```

### Phase 3: 智能扩展（2-3 周）

```
□ AI 能力
  ├── 记忆系统
  ├── 本地指令识别
  └── 主动关怀定时任务

□ 环境感知（可选）
  ├── 温湿度/光线传感器
  └── 环境提醒逻辑

□ 智能家居（可选）
  ├── MQTT 协议对接
  └── 设备控制指令
```

### Phase 4: 趣味玩法（1-2 周）

```
□ 小游戏
  ├── 猜数字
  └── 成语接龙

□ 桌面宠物
  ├── 自主行为状态机
  └── 互动反馈

□ 彩蛋
  ├── 性格切换
  ├── 树洞模式
  └── 摇一摇冷知识
```

### Phase 5: 优化打磨（持续）

```
□ 功耗优化
□ 响应速度优化
□ 外壳设计与制作
□ OTA 升级支持
□ 文档与开源
```

---

## 附录 A：市场方案对比参考

### A.1 商业产品技术路线

| 产品 | 主控 | 唤醒方案 | 供电 | 特点 |
|------|------|---------|------|------|
| 小爱同学 mini | 全志 R16 | 本地检测 | 插电 | 米家生态 |
| 天猫精灵 | 联发科 MT8516 | 本地检测 | 插电 | 阿里生态 |
| Amazon Echo | 专用芯片 | 硬件唤醒 | 插电 | Alexa 生态 |
| **Wallace** | ESP32-S3 | WakeNet | 电池 | 开源、DIY |

### A.2 为什么选择 ESP32-S3

| 维度 | ESP32-S3 | 专用语音芯片 | 树莓派 |
|------|---------|------------|-------|
| 成本 | ¥35-50 | ¥50-100+ | ¥200+ |
| 功耗 | 25mA 监听 | <1mA | 500mA+ |
| 开发难度 | 中等 | 高 | 低 |
| 灵活性 | 高 | 低 | 高 |
| 电池续航 | 3-5 天 | 数周 | 几小时 |
| 适合场景 | DIY/桌面 | 专业产品 | 服务器 |

**结论**：ESP32-S3 在成本、功耗、灵活性之间取得了最佳平衡，适合 Wallace 的定位。

---

## 附录 B：开发调试建议

### B.1 推荐开发顺序

1. **先跑通最小系统**：屏幕 + 麦克风 + 喇叭
2. **再加入唤醒词**：确保基础交互正常
3. **然后逐步扩展**：情绪、灯带、传感器
4. **最后优化打磨**：功耗、外壳、细节

### B.2 调试工具

| 工具 | 用途 |
|------|------|
| USB 串口 | 日志输出 |
| 万用表 | 电压/电流测量 |
| 逻辑分析仪 | I2S/SPI 信号分析 |
| Audacity | 音频录制/分析 |

### B.3 常见问题排查

```
问题：麦克风没声音
→ 检查 L/R 引脚是否接地
→ 检查 I2S 引脚配置
→ 用示波器/逻辑分析仪看 BCLK/WS 信号

问题：喇叭没声音
→ 检查 5V 供电是否正常
→ 检查 I2S_NUM 是否正确（应该用 I2S_NUM_1）
→ 检查 SD 引脚是否悬空或接高

问题：屏幕不亮
→ 检查 BLK 背光引脚
→ 检查 SPI 引脚配置
→ 确认 CS 片选正确
```

---

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v1 | - | 初始方案（STM32 + ESP8266） |
| v2 | - | 升级为 ESP32-S3 单芯片方案 |
| v3 | - | 新增语音唤醒、硬件审核、功耗优化 |
| v4 | 2026-02 | 新增情绪系统、眼神追踪、环境感知、智能家居、趣味玩法 |
| v4.1 | 2026-02 | 完善开源唤醒词方案、补充 PlatformIO 配置示例、优化混合唤醒策略 |

---

> **Wallace** - 不只是一个语音助手，而是一个有情感、有个性、会陪伴你的桌面 AI 伙伴。
> 
> 🎭 它会开心、会难过、会好奇  
> 👀 它会看着你、跟随你的方向  
> 💬 它会记住你、主动关心你  
> 🎮 它会陪你玩、给你惊喜  
> 
> **让 AI 真正"活"起来。**
