# Wallace v4.2 采购清单（基于现有器件）

> 说明：本清单依据 v4.2 BOM 与当前器件库存对比整理。
> **v4.2 更新**：开发板升级为 ESP32-S3 N32R16V（32MB Flash + 16MB PSRAM），提供更充裕的存储空间和内存资源。

## 一、确定需要购买（核心必选缺口）

| 物品 | 数量 | 参考价/件 | 备注 |
|---|---:|---:|---|
| ESP32-S3 开发板 N32R16V | 2 | ¥45–65 | 需 N32R16V，Type‑C，双 USB，32MB Flash + 16MB PSRAM |
| INMP441 麦克风 | 1 | ¥8–12 | 现有 1 个，补 1 个 |
| MAX98357A 功放 | 2 | ¥6–10 | I2S 功放 |
| TP4056 充电模块 | 2 | ¥3–5 | Type‑C 带保护 |
| MT3608 升压模块 | 2 | ¥2–4 | 升压到 5V |
| WS2812B 环形灯带 | 1 | ¥5–10 | 12 颗/环 |
| TTP223 触摸模块 | 2 | ¥1–2 | 备用唤醒 |
| 100μF 电解电容 | 5 | ¥1（整包） | 升压滤波 |
| 杜邦线 + 排针 | 1 批 | ¥10 | 尽量短 |

## 二、待确认后再决定

| 物品 | 数量 | 参考价/件 | 需要确认 |
|---|---:|---:|---|
| GC9A01 1.28 寸圆屏 | 1 | ¥15–25 | 你现有为 1.28 寸圆屏，需确认驱动芯片是否 GC9A01 |
| 18650 电池 + 电池盒 | 1 组 | ¥15–25 | 你已有 18650 电池与电池盒，容量与串并方式确认 |
| SS12D00 拨动开关 | 5 | ¥0.5 | 可用现有 KCD1/PBS/SS12D10 替代，尺寸确认 |
| 4Ω3W 带腔体喇叭 | 1 | ¥5–10 | 你有 4Ω3W 喇叭，需确认是否带音腔 |

## 三、可选扩展（按功能选择）

| 物品 | 数量 | 参考价/件 | 功能 |
|---|---:|---:|---|
| VL53L0X | 1 | ¥8–12 | 眼神追踪 |
| DHT22 | 1 | ¥8–12 | 温湿度 |
| BH1750 | 1 | ¥3–5 | 光线感应 |
| OV2640 | 1 | ¥15–20 | 人脸检测（你现有 OV7670 不兼容） |
| MQ‑135 | 1 | ¥8–12 | 空气质量 |
| SD 卡模块 | 1 | ¥3–5 | 本地存储（你已有，可不买） |
| MPU6050 | 1 | ¥5–8 | 摇一摇彩蛋（你已有，可不买） |
| 物理按钮 | 2 | ¥0.5 | 彩蛋触发（你已有轻触开关盒） |

## 四、v4.2 配置变更说明

### 开发板升级：N16R8 → N32R16V

| 规格 | v4.1 (N16R8) | v4.2 (N32R16V) |
|---|---|---|
| Flash | 16MB | 32MB |
| PSRAM | 8MB | 16MB |
| 参考价格 | ¥35–50 | ¥45–65 |

### 升级优势

1. **更大的 Flash 空间**：可存储更大的语音模型、更多音效资源
2. **更充裕的 PSRAM**：支持更复杂的动画缓存、更流畅的多任务处理
3. **扩展潜力**：为未来功能升级预留空间

### 配置调整

使用 N32R16V 时，需在 `platformio.ini` 中调整以下配置：

```ini
; platformio.ini (v4.2 N32R16V 配置)
[env:esp32s3]
platform = espressif32
board = esp32-s3-devkitc-1
framework = espidf

; 锁定 ESP-IDF 版本（与 ESP-SR/ESP-ADF 兼容）
platform_packages = 
    framework-espidf @ ~5.1.0

; PSRAM 配置（N32R16V）
board_build.arduino.memory_type = qio_opi
board_build.psram_mode = opi

; Flash 配置（32MB）
board_upload.flash_size = 32MB

; 串口配置
monitor_speed = 115200
upload_speed = 921600

; 额外组件路径（ESP-SR、ESP-ADF 等）
board_build.cmake_extra_args = 
    -DEXTRA_COMPONENT_DIRS=${PROJECT_DIR}/components

; 分区表（为语音模型预留更大空间）
board_build.partitions = partitions_v42.csv
```

### 自定义分区表示例（partitions_v42.csv）

针对 32MB Flash 优化的分区表：

```csv
# Name,   Type, SubType, Offset,   Size,    Flags
nvs,      data, nvs,     0x9000,   0x6000,
phy_init, data, phy,     0xf000,   0x1000,
factory,  app,  factory, 0x10000,  0x600000,
model,    data, spiffs,  0x610000, 0x1F0000,
storage,  data, spiffs,  0x800000, 0x800000,
```

> 注意：以上分区表利用了 N32R16V 更大的 Flash 空间，为固件、模型和存储分配了更充裕的容量。