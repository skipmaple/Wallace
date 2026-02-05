# Wallace 项目嵌入式开发学习路线图

> **你的情况**：硬件已到手 + 边学边做模式 + 10 倍学习力
> **预计完成时间**：6-10 周（现实估计，I2S 音频是最大挑战）

---

## Day 0：硬件验证（到货后立即执行！）

⚠️ **在开始任何开发之前，必须先验证硬件是否正确！**

### 0.1 检查开发板型号

拍照对比官方产品图，确认：
- [ ] 芯片丝印包含 "ESP32-S3"
- [ ] 模块型号为 N32R16V（32MB Flash / 16MB PSRAM）
- [ ] 有 Type-C USB 口
- [ ] 有 BOOT 和 RST 两个按键

**万一买错了**：
- 买成 ESP32（无 S3）→ 不支持 I2S 同时收发，需要退换
- 买成 N16R8 → 可以用，但 PSRAM 只有 8MB
- 买成 WROOM-1 → Flash 只有 4MB，空间可能不够

### 0.2 USB 连接测试

1. 用**数据线**（不是充电线！）连接电脑
2. 打开设备管理器，查看"端口 (COM 和 LPT)"
3. 应该出现 "USB Serial Device (COM3)" 或类似
4. **如果显示感叹号**：下载安装 CP2102/CP2104 驱动
5. **如果完全不识别**：换一根线，很多线只能充电不能传数据

### 0.3 首次上电观察

- [ ] 没有烟雾或焦糊味（如有立即断电！）
- [ ] ESP32 的电源指示灯亮起
- [ ] USB 连接后电脑能识别

### 0.4 准备调试工具

| 工具 | 必要性 | 价格 | 用途 |
|------|--------|------|------|
| **万用表** | 必须 | ¥30-50 | 检查电压、确认 VCC/GND 不短路 |
| **逻辑分析仪** | 强烈建议 | ¥50-100 | I2S/SPI/I2C 信号分析，调试音频必备 |
| **面包板** | 建议 | ¥10 | 方便接线调试 |
| **杜邦线** | 必须 | ¥8 | 公对母、母对母各一套 |

---

## 第一天行动指南（环境搭建）

### Step 1: 安装 ESP-IDF 开发环境（2-4 小时，预留足够时间！）

**Windows 推荐方式**：ESP-IDF Tools Installer

```bash
# 1. 下载官方安装器
# https://dl.espressif.com/dl/esp-idf/

# 2. 安装路径建议（避免中文和空格！）
#    - 安装到 C:\Espressif（不要装在 Program Files）
#    - 工作目录用 C:\esp（不要用 ~/esp，那是 Linux 写法）

# 3. 安装时勾选：
#    - ESP-IDF v5.1.x（推荐稳定版）
#    - Python 3.11
#    - Git for Windows

# 4. 安装完成后，从开始菜单打开 "ESP-IDF 5.1 PowerShell"
#    （注意：用 PowerShell，不要用 CMD）

# 5. 验证安装
idf.py --version
```

**⚠️ 常见安装问题**：
- 安装卡住 → 检查网络，可能需要翻墙下载工具链
- Python 冲突 → 卸载系统其他 Python 版本，或用 ESP-IDF 自带的
- 路径太长 → 安装到 C:\Espressif，不要用 Program Files

**VSCode 扩展安装**：
1. 安装 "ESP-IDF" 扩展
2. Ctrl+Shift+P → "ESP-IDF: Configure ESP-IDF Extension"
3. 选择已安装的 ESP-IDF 路径（C:\Espressif\frameworks\esp-idf-v5.1.x）
4. **如果配置失败**：删除 `%USERPROFILE%\.vscode\extensions` 中的 espressif 文件夹，重新安装

### Step 2: 第一个项目 - Blink LED（1-2 小时）

```bash
# Windows PowerShell 命令（不是 Linux！）
cd C:\esp
xcopy /E /I %IDF_PATH%\examples\get-started\blink blink
cd blink

# 配置目标芯片
idf.py set-target esp32s3

# 配置 GPIO（ESP32-S3-DevKitC 板载 LED 在 GPIO 48）
idf.py menuconfig
# → Example Configuration → Blink GPIO number → 48

# 编译
idf.py build

# 烧录（USB 连接开发板）
idf.py -p COM3 flash    # Windows，COM 端口号根据实际情况
idf.py -p /dev/ttyUSB0 flash  # Linux

# 查看串口输出
idf.py -p COM3 monitor
# Ctrl+] 退出
```

**成功标志**：板载 LED 闪烁 + 串口打印 "Turning the LED ON/OFF"

**⚠️ 烧录失败常见原因**：
| 错误 | 原因 | 解决 |
|------|------|------|
| `No serial data received` | USB 线只能充电 | 换数据线 |
| `Failed to connect` | 没进下载模式 | 按住 BOOT，按一下 RST，松开 BOOT |
| `Permission denied: COM3` | 端口被占用 | 关闭其他串口软件（如 PuTTY） |

### Step 3: 连接 WiFi（1 小时）

```bash
# Windows PowerShell 命令
xcopy /E /I %IDF_PATH%\examples\wifi\getting_started\station C:\esp\wifi_test
cd C:\esp\wifi_test

idf.py set-target esp32s3
idf.py menuconfig
# → Example Configuration
#   → WiFi SSID: 你的WiFi名
#   → WiFi Password: 你的WiFi密码

idf.py build && idf.py -p COM3 flash monitor
```

**成功标志**：串口输出 "got ip: 192.168.x.x"

### Step 4: 点亮 GC9A01 圆形屏幕（1-2 小时）

这是你的**第一个真正挑战** — 需要接线 + 驱动库配置。

**接线（来自 doc/spec.md 第 212-222 行）**：

| GC9A01 引脚 | ESP32-S3 GPIO | 说明 |
|------------|---------------|------|
| VCC | 3.3V | 供电 |
| GND | GND | 接地 |
| SCL (SCK) | **GPIO 12** | SPI 时钟 |
| SDA (MOSI) | **GPIO 11** | SPI 数据 |
| RES (RST) | **GPIO 10** | 复位 |
| DC | **GPIO 9** | 数据/命令选择 |
| CS | **GPIO 46** | 片选 |
| BLK | **GPIO 45** | 背光（可选，接 3.3V 常亮） |

**使用 LovyanGFX 库**：

```bash
# 在项目的 components 目录下克隆
mkdir -p ~/esp/my_display/components
cd ~/esp/my_display/components
git clone https://github.com/lovyan03/LovyanGFX.git
```

创建 `main/main.cpp`：
```cpp
#include <LovyanGFX.hpp>

class LGFX : public lgfx::LGFX_Device {
    lgfx::Panel_GC9A01 _panel;
    lgfx::Bus_SPI _bus;
public:
    LGFX(void) {
        auto cfg = _bus.config();
        cfg.spi_host = SPI2_HOST;
        cfg.freq_write = 40000000;
        cfg.pin_sclk = 12;   // SCK
        cfg.pin_mosi = 11;   // MOSI
        cfg.pin_dc   = 9;    // DC
        _bus.config(cfg);
        _panel.setBus(&_bus);

        auto panel_cfg = _panel.config();
        panel_cfg.pin_cs   = 46;  // CS
        panel_cfg.pin_rst  = 10;  // RST
        panel_cfg.panel_width  = 240;
        panel_cfg.panel_height = 240;
        _panel.config(panel_cfg);

        setPanel(&_panel);
    }
};

static LGFX lcd;

extern "C" void app_main(void) {
    lcd.init();
    lcd.setRotation(0);
    lcd.fillScreen(TFT_BLACK);

    // 画一个简单的眼睛
    lcd.fillCircle(120, 120, 80, TFT_WHITE);  // 眼白
    lcd.fillCircle(120, 120, 40, TFT_BLACK);  // 瞳孔
    lcd.fillCircle(130, 110, 15, TFT_WHITE);  // 高光
}
```

**成功标志**：圆形屏幕显示一只简单的眼睛！

**⚠️ 屏幕不亮的排查步骤**：
1. 检查背光 BLK 是否接了（可以直接接 3.3V 测试）
2. 用万用表测量 VCC 是否有 3.3V
3. 检查 SPI 引脚是否接对（MOSI/MISO 容易接反）
4. 降低 SPI 频率到 10MHz 试试（`cfg.freq_write = 10000000`）
5. 如果还是不亮，可能是屏幕坏了，换一个试试

---

## 第二天目标：验证硬件容量

在点亮屏幕后（或遇到问题前），先验证开发板的 Flash 和 PSRAM 容量：

```c
// 在 app_main 中添加以下代码
#include "esp_chip_info.h"
#include "esp_psram.h"
#include "esp_flash.h"

void verify_hardware(void) {
    esp_chip_info_t chip_info;
    esp_chip_info(&chip_info);

    ESP_LOGI("HW", "芯片: ESP32-S3, 核心数: %d", chip_info.cores);

    uint32_t flash_size;
    esp_flash_get_size(NULL, &flash_size);
    ESP_LOGI("HW", "Flash: %lu MB", flash_size / (1024 * 1024));  // 期望 32MB

    ESP_LOGI("HW", "PSRAM: %d MB", esp_psram_get_size() / (1024 * 1024));  // 期望 16MB
}
```

**如果 PSRAM 显示 0**：说明 PSRAM 未启用或开发板型号不对，见下方配置。

### Step 5: 关键配置（必须完成）

#### 5.1 启用 PSRAM（16MB 内存扩展）

ESP32-S3 N32R16V 有 16MB PSRAM，必须手动启用：

```bash
idf.py menuconfig
# → Component config
#   → ESP PSRAM
#     → [*] Support for external, SPI-connected RAM
#     → SPI RAM config
#       → Mode: Octal Mode PSRAM
#       → [*] Initialize SPI RAM during startup
#       → [*] Run malloc() on external RAM
```

验证 PSRAM 是否启用：
```c
#include "esp_heap_caps.h"
size_t psram_size = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
ESP_LOGI("PSRAM", "Total: %d bytes", psram_size);  // 应该显示约 16MB
```

#### 5.2 CMakeLists.txt 配置

ESP-IDF 项目的组件依赖需要在 `CMakeLists.txt` 中声明：

```cmake
# main/CMakeLists.txt 示例
idf_component_register(
    SRCS "main.cpp"
    INCLUDE_DIRS "."
    REQUIRES driver esp_timer esp_wifi nvs_flash  # 声明依赖的组件
)
```

如果使用外部组件（如 LovyanGFX），在项目根目录的 `CMakeLists.txt` 中添加：
```cmake
set(EXTRA_COMPONENT_DIRS "components")  # 指向 components 目录
```

---

## 接线安全指南（新手必读！）

### ⚠️ 接错会烧板子的危险操作

| 危险程度 | 错误操作 | 后果 | 预防 |
|---------|---------|------|------|
| **致命** | 5V 接到 3.3V 设备 | 烧毁传感器/屏幕 | 红线=5V，橙线=3.3V |
| **致命** | GND 和 VCC 接反 | 烧毁芯片 | 黑线永远是 GND |
| **严重** | I2C 的 SDA/SCL 接反 | 设备无响应 | A在C前，SDA在SCL后 |
| **严重** | SPI 的 MOSI/MISO 接反 | 屏幕不亮 | MOSI = Master Out |

### 每次接线前的检查清单

```
上电前必检（每次改动接线后都要做）：
[ ] 1. ESP32 USB 已拔出
[ ] 2. 用万用表检查 VCC-GND 不短路（蜂鸣档不响）
[ ] 3. 所有线连接牢固，没有松动
[ ] 4. 3.3V 设备（屏幕、传感器）没有接到 5V
[ ] 5. 所有 GND 都连在一起

上电后观察：
[ ] 1. 没有烟雾或焦糊味（有则立即断电！）
[ ] 2. ESP32 电源灯正常亮起
[ ] 3. 用万用表测量 3.3V 和 5V 轨电压正常
```

### 推荐的接线顺序（分阶段，降低风险）

**第 1 周：最小系统**
```
Day 1-2: 仅 USB 连接，不接任何外设（跑 Blink）
Day 3-4: 只接屏幕 GC9A01（7 根线）
Day 5-7: 验证屏幕正常后再继续
```

**第 2 周：音频模块**
```
Day 8-9: 加入麦克风 INMP441（5 根线）
Day 10-11: 加入功放 MAX98357A + 喇叭（5 根线）
          注意：功放需要 5V，从 MT3608 供电！
Day 12-14: 测试录音 → 播放
```

**第 3 周：传感器**
```
Day 15: I2C 总线 + VL53L0X 测距（4 根线）
Day 16: 加入 DHT20、BH1750（共用 I2C 总线）
Day 17+: 其他传感器和 RGB 灯带
```

---

## 完整引脚接线图（核心模块）

保存这张表，接线时对照使用：

```
┌─────────────────────────────────────────────────────────────────┐
│                     ESP32-S3 N32R16V 核心接线                     │
├─────────────────────────────────────────────────────────────────┤
│  【I2S 麦克风 - INMP441】                                         │
│     SCK (BCLK) ─── GPIO 41                                       │
│     WS  (LRC)  ─── GPIO 42                                       │
│     SD  (DOUT) ─── GPIO 2                                        │
│     VDD        ─── 3.3V                                          │
│     L/R        ─── GND（左声道）                                   │
│                                                                  │
│  【I2S 功放 - MAX98357A】                                         │
│     BCLK ─── GPIO 15                                             │
│     LRC  ─── GPIO 16                                             │
│     DIN  ─── GPIO 17                                             │
│     Vin  ─── 5V（从 MT3608）                                      │
│                                                                  │
│  【SPI 屏幕 - GC9A01】                                            │
│     SCK  ─── GPIO 12                                             │
│     MOSI ─── GPIO 11                                             │
│     DC   ─── GPIO 9                                              │
│     RST  ─── GPIO 10                                             │
│     CS   ─── GPIO 46                                             │
│     BLK  ─── GPIO 45（或接 3.3V 常亮）                             │
│                                                                  │
│  【I2C 传感器总线】（所有传感器共用）                                │
│     SDA ─── GPIO 6                                               │
│     SCL ─── GPIO 7                                               │
│     ├── VL53L0X  (0x29) 测距                                     │
│     ├── BH1750   (0x23) 光线                                     │
│     ├── DHT20    (0x38) 温湿度                                   │
│     └── MPU6050  (0x68) 姿态                                     │
│                                                                  │
│  【RGB 灯带 - WS2812B】                                           │
│     DIN ─── GPIO 48                                              │
│     VCC ─── 5V                                                   │
│                                                                  │
│  【其他】                                                         │
│     TTP223 触摸 ─── GPIO 1                                        │
│     物理按钮    ─── GPIO 0                                        │
│     MQ-135 AO  ─── GPIO 4 (ADC)                                  │
│     电池电压    ─── GPIO 5 (ADC)                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 背景分析

### 你的现有优势
- **Ruby on Rails 主力开发** → 理解 Web 架构、API 设计、异步处理
- **基础运维经验** → 熟悉 Linux 环境、命令行、部署流程
- **Python/Go/C/C++ 会语法** → 能看懂代码，需要加强实战
- **10 倍学习力** → 可以采用高强度、并行学习策略

### 项目现状
| 部分 | 状态 | 你需要做的 |
|------|------|-----------|
| PC 服务端 | ✅ 完成 | 理解代码，按需修改 |
| 硬件设计 | ✅ 完成 | 按 BOM 采购、焊接组装 |
| ESP32 固件 | ❌ 未开始 | **核心工作：从零编写** |

### 核心挑战
ESP32 固件需要用 **C/C++** 编写，涉及：
1. 实时操作系统 (FreeRTOS) 多任务调度
2. 硬件外设驱动 (I2S/I2C/SPI/GPIO)
3. 音频流处理 (PCM 采集/播放)
4. 网络通信 (WiFi + WebSocket)
5. 图形渲染 (圆形 LCD 动画)
6. 功耗管理状态机

---

## 学习路线图（8-10 周现实估计）

> **说明**：原计划 4-6 周过于乐观。根据新手实际情况，I2S 音频是最大挑战，可能卡 2-3 周。调整为 8-10 周更现实，但 10 倍学习力可能 6-8 周完成。

### 第一阶段：环境搭建 + 建立信心（第 1 周）

#### 1.1 采购硬件
按 `doc/purchase-list.md` 采购（~¥270），重点：
- ESP32-S3-N32R16V 开发板（32MB Flash / 16MB PSRAM）
- GC9A01 圆形屏
- INMP441 麦克风 + MAX98357A 功放 + 喇叭
- 基础传感器套件

#### 1.2 搭建开发环境
```bash
# 安装 ESP-IDF（官方 SDK）
# Windows 推荐 ESP-IDF Tools Installer
# 或 VSCode + ESP-IDF 扩展

# 验证安装
idf.py --version
```

#### 1.3 入门项目（每个 2-4 小时）
| 序号 | 项目 | 目标 |
|------|------|------|
| 1 | Blink LED | 理解 GPIO、CMake 构建、烧录流程 |
| 2 | WiFi 连接 | 理解 WiFi 配置、事件回调 |
| 3 | UART 打印 | 理解日志系统、调试方法 |

**学习资源**：
- ESP-IDF 官方文档：https://docs.espressif.com/projects/esp-idf/
- ESP32-S3 技术手册（中文）

---

### 第二阶段：屏幕 + 传感器（第 2-3 周）

先做简单的，建立信心：
- **第 2 周**：屏幕驱动 + 简单动画
- **第 3 周**：I2C 传感器（相对简单）

### 第三阶段：音频系统（第 4-6 周）—— 最大挑战！

#### 3.1 I2S 音频（核心难点，2-3 周）

**目标**：实现麦克风录音 → PCM 数据 → 喇叭播放

```c
// 核心概念
// I2S = Inter-IC Sound，用于数字音频传输
// DMA = Direct Memory Access，硬件自动搬运数据，不占 CPU

// ⚠️ 重要：ESP-IDF 5.x 使用新版 channel-based API
// 旧版 i2s_config_t 已废弃！

#include "driver/i2s_std.h"

// 麦克风配置示例（ESP-IDF 5.x 新版 API）
i2s_chan_handle_t rx_chan;
i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
i2s_new_channel(&chan_cfg, NULL, &rx_chan);

i2s_std_config_t std_cfg = {
    .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(16000),
    .slot_cfg = I2S_STD_MSB_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
    .gpio_cfg = {
        .mclk = I2S_GPIO_UNUSED,
        .bclk = GPIO_NUM_41,
        .ws = GPIO_NUM_42,
        .dout = I2S_GPIO_UNUSED,
        .din = GPIO_NUM_2,
    },
};
i2s_channel_init_std_mode(rx_chan, &std_cfg);
i2s_channel_enable(rx_chan);

// 读取音频数据
size_t bytes_read;
i2s_channel_read(rx_chan, buffer, sizeof(buffer), &bytes_read, portMAX_DELAY);
```

**⚠️ I2S 是整个项目最难的部分，预计需要 2-3 周！**

**分步练习（不要跳步！）**：

```
Step 1: 理解 I2S 协议（Day 1）
- 目标：能画出 BCLK, WS, SD 三根线的时序图
- 阅读：https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/i2s.html

Step 2: 最小麦克风测试（Day 2-3）
- 只配置 I2S 接收
- 读取数据打印到串口
- 成功标准：对着麦克风说话，串口数值有明显变化

Step 3: 最小喇叭测试（Day 4-5）
- 生成一个 1kHz 正弦波数组
- 通过 I2S 发送到喇叭
- 成功标准：听到持续的"嘟"音

Step 4: 环回测试（Day 6-7）
- 麦克风数据直接送到喇叭
- 成功标准：能听到自己说话的回声（延迟 < 200ms 即可）

Step 5: WAV 文件播放（Week 2）
- 先用 SPIFFS（不要用 SD 卡，减少复杂度）
- 嵌入一个测试 WAV 文件
- 成功标准：播放出预设的语音
```

**常见问题排查**：
- 无声音 → 检查 INMP441 的 L/R 引脚是否接 GND
- 杂音/爆音 → DMA 缓冲区太小，增加 `dma_buf_len`
- 声音断断续续 → CPU 负载太高，用更大的缓冲区或降低采样率

---

### 第四阶段：FreeRTOS 多任务（第 7 周）

#### 4.1 核心概念
```c
// ESP32 双核 + FreeRTOS 可以真正并行执行任务
// 核心 0：WiFi/蓝牙协议栈（系统占用）
// 核心 1：用户任务（音频处理、屏幕刷新等）

// 创建任务
xTaskCreatePinnedToCore(
    audio_task,      // 任务函数
    "Audio",         // 任务名
    8192,            // 栈大小
    NULL,            // 参数
    5,               // 优先级（数字越大优先级越高）
    &audio_handle,   // 任务句柄
    1                // 绑定到核心 1
);
```

#### 4.2 任务间通信
- **Queue（队列）**：任务间传递数据（如音频帧）
- **Semaphore（信号量）**：同步/互斥
- **Event Group（事件组）**：多事件等待

#### 4.3 Wallace 的任务架构设计
```
┌─────────────────────────────────────────────────────┐
│                    ESP32-S3 任务架构                 │
├─────────────────────────────────────────────────────┤
│ Core 0 (系统)                                        │
│   ├── WiFi Task (系统)                               │
│   └── WebSocket Task (用户)                          │
│                                                      │
│ Core 1 (用户)                                        │
│   ├── Audio Capture Task (I2S RX → Queue)            │
│   ├── Audio Playback Task (Queue → I2S TX)           │
│   ├── Display Task (动画渲染)                         │
│   ├── Sensor Task (周期性读取传感器)                   │
│   └── LED Task (RGB 灯效控制)                         │
│                                                      │
│ 任务间通信                                            │
│   ├── audio_tx_queue: WebSocket → Playback           │
│   ├── audio_rx_queue: Capture → WebSocket            │
│   ├── emotion_event: WebSocket → Display/LED         │
│   └── sensor_queue: Sensor → WebSocket               │
└─────────────────────────────────────────────────────┘
```

---

### 第五阶段：网络 + WebSocket（第 8 周）

#### 5.1 WiFi 连接管理
- 配网方式：SmartConfig / Web 配网页面
- 断线重连机制
- 连接状态指示（LED 颜色）

#### 5.2 WebSocket 客户端

**⚠️ 重要**：`esp_websocket_client` 不是 ESP-IDF 核心组件，需要单独安装：

```bash
# 在项目目录下运行
idf.py add-dependency "espressif/esp_websocket_client^1.2.2"
```

或在项目根目录创建 `idf_component.yml`：
```yaml
dependencies:
  espressif/esp_websocket_client: "^1.2.2"
```

```c
// 使用 esp_websocket_client 组件与 PC 服务端通信

// JSON 消息类型（参考 server/wallace/ws/protocol.py）

// ESP32 → Server（JSON 消息）
// - ping: 心跳
// - audio_start / audio_end: 音频录制开始/结束
// - sensor: {temp, humidity, light, air_quality}
// - proximity: {distance, user_present}
// - device_state: {battery_pct, power_mode, wifi_rssi}
// - event: {event: "personality_switch"|"treehouse_mode"|"shake"|"touch", value}
// - local_cmd: {action: "开灯"|"关灯"等}

// Server → ESP32（JSON 消息）
// - tts_start: {mood} 开始播放语音
// - tts_end: 语音播放结束
// - tts_cancel: 取消语音播放（被打断）
// - text: {content, partial, mood} 文字内容（可选显示）
// - care: {content, mood} 主动关怀推送
// - sensor_alert: {alert, suggestion} 传感器告警
// - pong: 心跳响应

// 二进制消息（直接发送 PCM 数据，不经过 JSON）
// - ESP32 → Server: PCM 音频帧（16kHz 16bit 单声道 小端）
// - Server → ESP32: TTS 音频帧（同格式）
```

#### 5.3 音频流传输
```c
// 上行：麦克风 PCM → WebSocket 二进制帧
// 下行：WebSocket 二进制帧 → 播放队列 → 喇叭

// 关键参数
// 采样率: 16000 Hz
// 位深: 16 bit
// 声道: 单声道
// 字节序: 小端
```

---

### 第六阶段：整合 + 联调（第 9-10 周）

#### 6.1 完整状态机
```
IDLE ──(唤醒词)──▶ LISTENING ──(VAD静音)──▶ PROCESSING
  ▲                    │                        │
  │                    │(超时)                  │(收到音频)
  │                    ▼                        ▼
  └────────────────── IDLE ◀────────────── SPEAKING
                                              │
                                        (播放完成)
```

#### 6.2 功耗管理
```c
// 5 个功耗等级
typedef enum {
    POWER_FULL,      // 全速运行（对话中）
    POWER_NORMAL,    // 正常待机（WiFi 连接）
    POWER_SAVING,    // 省电模式（降频）
    POWER_ULTRA_LOW, // 超低功耗（仅唤醒词检测）
    POWER_SLEEP,     // 深度睡眠（定时唤醒）
} power_state_t;
```

#### 6.3 眼睛动画系统
- 眨眼（随机间隔）
- 情绪表情（开心/害羞/思考/困倦...）
- 眼神追踪（根据 VL53L0X 距离）
- 闲置动画（左右看、眯眼）

#### 6.4 与服务端联调
1. 启动 PC 服务端
2. ESP32 连接 WebSocket
3. 测试完整对话流程

#### 6.5 常见问题排查
- 音频杂音/爆音 → 检查 I2S 时序、DMA 缓冲
- 屏幕闪烁 → 检查 SPI 频率、刷新策略
- WiFi 断连 → 检查信号强度、重连逻辑
- 内存不足 → 使用 PSRAM、优化缓冲区

---

## 附：I2C 传感器参考（相对简单）

#### I2C 传感器（3-4 天）

**目标**：读取温湿度、光线、距离传感器

```c
// I2C 总线扫描
// 项目中 4 个设备共用一条 I2C 总线
// VL53L0X (0x29), BH1750 (0x23), DHT20 (0x38), MPU6050 (0x68)
```

**练习项目**：
1. 扫描 I2C 总线，打印所有设备地址
2. 读取 DHT20 温湿度
3. 读取 VL53L0X 距离（用于眼神追踪）

#### SPI 屏幕驱动（3-4 天）

**目标**：在圆形屏幕上显示图形

```c
// 推荐使用 LovyanGFX 库
// 支持 GC9A01 圆形屏，提供高级绘图 API
```

**练习项目**：
1. 填充颜色、画基本图形
2. 显示静态眼睛图片
3. 简单动画（眼睛眨眼）

---

## 并行学习策略（利用 10 倍效率）

### 每日时间分配（假设每天 4+ 小时）

```
上午：理论学习（文档、视频）
下午：动手实践（写代码、烧录调试）
晚上：复盘总结（记笔记、整理代码）
```

### 推荐学习资源

| 类型 | 资源 | 说明 |
|------|------|------|
| **官方文档** | [ESP-IDF 编程指南](https://docs.espressif.com/projects/esp-idf/) | 权威参考，必读 |
| **视频教程** | B站搜"ESP32-S3 入门" | 中文友好 |
| **开源参考** | [ESP-BOX](https://github.com/espressif/esp-box) | 乐鑫官方语音助手，架构参考 |
| **库文档** | [LovyanGFX Wiki](https://github.com/lovyan03/LovyanGFX/wiki) | 屏幕驱动 |
| **Claude AI** | 你现在用的 | 随时问代码问题、调试帮助 |

### 关键原则

1. **先跑通再优化** — 先实现功能，再考虑性能
2. **善用 AI 辅助** — Claude 可以帮你写驱动代码、解释底层原理
3. **模块化开发** — 每个外设独立调试，最后整合
4. **保持与服务端协议一致** — 参考 `server/wallace/ws/protocol.py`

---

## 验收标准

完成本学习路线后，你应该能够：

- [ ] 独立编写 ESP32-S3 固件代码
- [ ] 实现麦克风录音 + 喇叭播放
- [ ] 驱动圆形屏幕显示眼睛动画
- [ ] 通过 WebSocket 与 PC 服务端通信
- [ ] 读取所有传感器数据
- [ ] 控制 RGB 灯效
- [ ] 实现完整的语音对话流程

**最终目标**：一个能听、能说、有表情、会互动的桌面 AI 伴侣机器人！

---

## Web 开发者概念类比

| 嵌入式概念 | Web 类比 | 关键区别 |
|-----------|----------|---------|
| FreeRTOS Task | Node.js Worker Thread | 协作式调度，需主动 yield |
| Queue | Redis/RabbitMQ | 内存中，固定大小，满了会阻塞 |
| Semaphore | 数据库锁 | 用于任务同步/互斥 |
| I2S DMA | Stream Pipeline | 硬件自动搬运，零 CPU 占用 |
| menuconfig | .env 环境变量 | 编译时确定，运行时不可变 |
| 分区表 | 数据库 Schema | 定义 Flash 存储布局 |
| PSRAM | Redis 缓存 | 大容量但访问稍慢的扩展内存 |

---

## 调试技巧

### 日志系统（类似 console.log）

```c
#include "esp_log.h"

static const char* TAG = "MyModule";

// 不同级别的日志
ESP_LOGE(TAG, "Error: %s", msg);    // 红色，错误
ESP_LOGW(TAG, "Warning: %d", val);  // 黄色，警告
ESP_LOGI(TAG, "Info: %s", info);    // 绿色，信息
ESP_LOGD(TAG, "Debug: 0x%x", hex);  // 白色，调试（默认不显示）
ESP_LOGV(TAG, "Verbose");           // 白色，详细（默认不显示）

// 在 menuconfig 中调整日志级别
// → Component config → Log output → Default log verbosity
```

### 错误检查宏

```c
// ESP_ERROR_CHECK 类似 assert，出错会打印堆栈并重启
esp_err_t ret = some_function();
ESP_ERROR_CHECK(ret);  // 如果 ret != ESP_OK，会 panic

// 更优雅的错误处理
if (ret != ESP_OK) {
    ESP_LOGE(TAG, "Failed: %s", esp_err_to_name(ret));
    return ret;
}
```

### 内存监控

```c
// 查看剩余内存
ESP_LOGI(TAG, "Free heap: %lu", esp_get_free_heap_size());
ESP_LOGI(TAG, "Free PSRAM: %lu", heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

// 在 PSRAM 中分配大缓冲区
uint8_t* audio_buf = heap_caps_malloc(1024 * 1024, MALLOC_CAP_SPIRAM);
```

---

## 常见坑 & 避坑指南

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 烧录失败 | 开发板没进 Download 模式 | 按住 BOOT 键，再按 RST，松开 RST |
| 屏幕不亮 | 背光没接 | BLK 接 GPIO 45 或直接接 3.3V |
| 麦克风无声 | L/R 没接 GND | INMP441 的 L/R 引脚接 GND |
| 喇叭杂音 | 供电不稳 | 加 100μF 电容，功放接 5V |
| I2C 扫不到设备 | 上拉电阻缺失 | 多数模块自带，检查接线是否松动 |
| WiFi 连不上 | 信号差/密码错 | 检查 SSID/密码，靠近路由器 |
| 编译报错找不到头文件 | 组件路径错误 | 检查 CMakeLists.txt 的 REQUIRES |

---

## 如何高效利用 Claude 辅助学习

你可以随时问我：

1. **代码问题**
   - "这段 I2S 配置代码是什么意思？"
   - "帮我写一个读取 DHT20 温湿度的函数"

2. **调试帮助**
   - "串口输出这个错误是什么原因？[粘贴错误日志]"
   - "屏幕只显示白色，可能是什么问题？"

3. **概念解释**
   - "DMA 是什么？为什么 I2S 要用 DMA？"
   - "FreeRTOS 的 Task 和线程有什么区别？"

4. **代码审查**
   - "帮我检查这段代码有没有问题 [粘贴代码]"
   - "这样写内存会不会泄漏？"

5. **架构建议**
   - "Wallace 的任务应该怎么划分？"
   - "音频缓冲区应该开多大？"

**提示**：遇到问题时，提供：
- 完整错误信息
- 相关代码片段
- 你已经尝试过的方法

这样我能更快帮你定位问题！

---

## 卡住时怎么办

### 调试 30 分钟无进展时

1. **停下来休息 10 分钟** — 盯着代码看不出问题
2. **用文字描述清楚问题** — 写下来往往能发现问题
3. **截图/拍照保留现场** — 方便求助

### 收集求助信息

在提问前，准备好：
- [ ] 完整的错误信息（不要截断）
- [ ] 相关代码片段
- [ ] 接线照片（如果是硬件问题）
- [ ] 你已经尝试过的方法

### 求助渠道

1. **Claude AI（我）** — 随时可以问，贴代码和错误信息
2. **ESP32 中文社区** — https://www.esp32.com/viewforum.php?f=26
3. **ESP-IDF GitHub Issues** — 搜索是否有人遇到过同样问题
4. **B站 ESP32 教程评论区** — 很多实战经验

### 常见卡点速查

| 现象 | 可能原因 | 快速解决 |
|------|---------|---------|
| 编译找不到头文件 | CMakeLists.txt 没配置 REQUIRES | 添加依赖组件 |
| 烧录超时 | 没进下载模式 | BOOT + RST 组合键 |
| 串口乱码 | 波特率不对 | 改成 115200 |
| WiFi 连不上 | SSID 有中文或空格 | 用纯英文 SSID |
| I2C 扫描无设备 | 接线问题 | 检查 SDA/SCL 是否接反 |
| 屏幕不亮 | 背光没接 | BLK 接 3.3V |
| 麦克风无声 | L/R 没接 GND | INMP441 的 L/R 接 GND |
| 喇叭杂音 | 供电不稳 | 加 100μF 电容 |

---

## MVP 优先级建议（快速出成果）

如果时间紧张，按这个顺序实现：

**必须实现（核心体验）**：
1. 屏幕显示眼睛
2. 麦克风录音 + 喇叭播放
3. WiFi + WebSocket 与服务端通信

**重要但可延后**：
4. VL53L0X 眼神追踪
5. DHT20 温湿度
6. RGB 灯效

**可选（后续再加）**：
7. 其他传感器
8. SD 卡存储
9. 复杂动画
10. 5 级功耗管理

---

## 关键文件路径速查

| 用途 | 路径 |
|------|------|
| 完整硬件规格 | `doc/spec.md` |
| 采购清单 | `doc/purchase-list.md` |
| 服务端架构 | `server/architecture.md` |
| WebSocket 协议定义 | `server/wallace/ws/protocol.py` |
| 情绪标签定义 | `server/wallace/emotion.py` |
| 测试示例 | `server/tests/` |
