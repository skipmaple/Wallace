from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

DOC_DIR = Path(r"Y:/work/Wallace/doc")
MD_PATH = DOC_DIR / "电子器件分类汇总.md"

CATEGORY_ORDER = [
    "传感器/摄像头",
    "其他",
    "开关/按键",
    "执行机构/机构件",
    "显示/人机界面",
    "电机驱动",
    "电源/供电/配线",
    "紧固件/结构件",
    "连接器/线材",
    "通信/无线模块",
]

CATEGORY_KEYWORDS = {
    "传感器/摄像头": [
        "传感", "摄像", "摄像头", "摄像机", "温湿度", "光线", "红外", "超声波",
        "测距", "激光", "麦克风", "加速度", "陀螺仪", "温度", "湿度", "气压",
        "烟雾", "气体", "空气", "人体", "雷达", "霍尔", "磁", "光敏",
        "指纹", "语音", "声音", "IMU", "MPU", "ADXL", "VL53", "BH1750",
        "DHT", "MQ", "OV", "INMP", "GY-",
    ],
    "开关/按键": [
        "开关", "按键", "按钮", "轻触", "触摸", "拨动", "船型", "自锁", "微动", "编码器",
    ],
    "执行机构/机构件": [
        "舵机", "电机", "马达", "机械", "支架", "云台", "电机夹", "螺旋桨", "减速",
        "齿轮", "轴", "滑轨", "风扇", "机臂",
    ],
    "显示/人机界面": [
        "显示", "屏", "OLED", "TFT", "LCD", "触摸屏", "液晶", "彩屏", "数码管", "面板",
    ],
    "电机驱动": [
        "电机驱动", "驱动板", "TB6612", "L298", "DRV", "H桥",
    ],
    "电源/供电/配线": [
        "电源", "供电", "电池", "充电", "升压", "降压", "稳压", "DC-DC", "电源模块",
        "充电器", "电源线", "电缆", "电解电容", "电容", "保险丝", "TP4056", "MT3608",
        "AMS", "电池盒", "电池扣", "滤波",
    ],
    "紧固件/结构件": [
        "螺丝", "螺母", "铜柱", "外壳", "机壳", "固定", "螺柱", "支撑", "连接柱",
    ],
    "连接器/线材": [
        "杜邦线", "排针", "接线", "端子", "排线", "插头", "插座", "连接器",
        "XH", "PH", "JST", "线材", "端子线", "Type-C",
    ],
    "通信/无线模块": [
        "WiFi", "蓝牙", "ESP", "NRF", "无线", "通信", "串口", "RF", "LoRa", "Zigbee",
    ],
}


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def build_link(value: str) -> str:
    text = normalize_text(value)
    if not text or text.lower() in {"nan", "none", "暂无"}:
        return "暂无"
    return f"[链接]({text})"


def classify_item(name: str) -> str:
    text = name or ""
    for category in CATEGORY_ORDER:
        for kw in CATEGORY_KEYWORDS.get(category, []):
            if kw.lower() in text.lower():
                return category
    return "其他"


def parse_markdown(md_text: str) -> Tuple[Dict[str, List[Tuple[str, str, int, str]]], List[str]]:
    """解析现有 markdown，返回 (分类数据, 已有来源文件列表)"""
    data: Dict[str, List[Tuple[str, str, int, str]]] = {cat: [] for cat in CATEGORY_ORDER}
    sources: List[str] = []
    current = None
    for line in md_text.splitlines():
        if line.startswith("- 来源文件："):
            sources = [s.strip() for s in line.replace("- 来源文件：", "").split(",")]
        if line.startswith("### "):
            current = line.replace("### ", "").strip()
            if current not in data:
                data[current] = []
            continue
        if not current:
            continue
        if not line.startswith("|"):
            continue
        if "商品名称" in line or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 4:
            continue
        name, model, qty, link = parts[0], parts[1], parts[2], parts[3]
        try:
            qty_value = int(float(qty))
        except ValueError:
            qty_value = 0
        data[current].append((name, model, qty_value, link))
    return data, sources


def load_excel_rows(xlsx_path: Path) -> List[Tuple[str, str, int, str]]:
    df = pd.read_excel(xlsx_path)
    df.columns = [normalize_text(c) for c in df.columns]

    def find_col(options):
        for col in df.columns:
            for opt in options:
                if opt in col:
                    return col
        return None

    name_col = find_col(["商品名称", "名称", "标题", "商品"])
    model_col = find_col(["型号", "款式", "规格", "型号款式"])
    qty_col = find_col(["数量", "件数", "数量(件)", "数量（件）"])
    link_col = find_col(["链接", "宝贝链接", "商品链接", "URL", "网址"])

    if not name_col:
        raise ValueError(f"无法识别商品名称列，现有列: {list(df.columns)}")

    rows = []
    for _, row in df.iterrows():
        name = normalize_text(row.get(name_col, ""))
        if not name:
            continue
        model = normalize_text(row.get(model_col, "")) if model_col else "暂无"
        qty_raw = row.get(qty_col, 1) if qty_col else 1
        try:
            qty = int(float(qty_raw))
        except (ValueError, TypeError):
            qty = 1
        link = build_link(row.get(link_col, "")) if link_col else "暂无"
        rows.append((name, model or "暂无", qty, link))
    return rows


def render_markdown(data: Dict[str, List[Tuple[str, str, int, str]]], sources: List[str]) -> str:
    total_qty = sum(row[2] for rows in data.values() for row in rows)
    lines = [
        "# 电子器件按功能分类汇总",
        "",
        "## 概览",
        "",
        f"- 来源文件：{', '.join(sources)}",
        f"- 分类数：{len([c for c in data.keys() if c])}",
        f"- 总数量：{total_qty}",
        "",
        "## 分类明细",
        "",
    ]

    for category in CATEGORY_ORDER:
        rows = data.get(category, [])
        if not rows:
            continue
        lines.append(f"### {category}")
        lines.append("")
        lines.append("| 商品名称 | 型号款式 | 数量 | 商品链接 |")
        lines.append("|---|---|---:|---|")
        for name, model, qty, link in rows:
            lines.append(f"| {name} | {model} | {qty} | {link} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python merge_order.py <xlsx文件路径>")
        print("示例: python merge_order.py Y:/work/Wallace/doc/订单数据\\ \\(5\\).xlsx")
        sys.exit(1)

    xlsx_path = Path(sys.argv[1])
    if not xlsx_path.exists():
        print(f"错误: 文件不存在 - {xlsx_path}")
        sys.exit(1)

    # 读取现有汇总
    if MD_PATH.exists():
        md_text = MD_PATH.read_text(encoding="utf-8")
        data, sources = parse_markdown(md_text)
    else:
        data = {cat: [] for cat in CATEGORY_ORDER}
        sources = []

    # 读取新 xlsx
    new_rows = load_excel_rows(xlsx_path)

    # 构建已有记录集合用于去重
    existing = set()
    for rows in data.values():
        for name, model, _, _ in rows:
            existing.add((name, model))

    # 合并新数据（去重）
    added = 0
    skipped = 0
    for name, model, qty, link in new_rows:
        if (name, model) in existing:
            skipped += 1
            continue
        category = classify_item(name)
        data.setdefault(category, []).append((name, model, qty, link))
        existing.add((name, model))
        added += 1

    # 追加来源文件名
    new_source = xlsx_path.name
    if new_source not in sources:
        sources.append(new_source)

    # 写入
    MD_PATH.write_text(render_markdown(data, sources), encoding="utf-8")
    print(f"完成: 新增 {added} 条, 跳过重复 {skipped} 条, 来源文件: {new_source}")


if __name__ == "__main__":
    main()
