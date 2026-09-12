#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lang.py — 界面语言：正统中文（默认） / English。
中文为原文（key），STRINGS 提供英文对照；T() 按当前语言返回。
切换语言后需重启程序生效。"""

# 由 main.py 在启动时按 kv 设置
LANG = "zh"

# 语言下拉在界面里的显示名（不翻译，按用户要求中文项写作“正统中文”）
LANGUAGE_LABELS = {"zh": "正统中文", "en": "English"}

STRINGS = {
    # 侧边栏 / 页面标题
    "仪表盘": "Dashboard",
    "模型与思考档位": "Models & Thinking Levels",
    "API 密钥": "API Keys",
    "用量明细": "Usage",
    "设置": "Settings",
    "chat2api 控制台": "chat2api Console",
    # 仪表盘
    "今日用量与后端连接状态 · 实时更新":
        "Today's usage and backend connection · live",
    "今日花费（人民币）": "Today's Cost (CNY)",
    "今日 Tokens": "Today's Tokens",
    "缓存命中": "Cache Hits",
    "今日请求": "Today's Requests",
    "↑ 较昨日 {d}": "↑ vs yesterday {d}",
    "↓ 较昨日 {d}": "↓ vs yesterday {d}",
    "输入 {i} · 输出 {o}": "in {i} · out {o}",
    "占输入 {p}": "{p} of input",
    "失败 {n}": "{n} failed",
    "可用模型": "available models",
    "后端": "Backend",
    "监听": "listening on",
    # 模型与思考档位
    "强制档位 = 服务端注入 reasoning_effort，对所有请求生效":
        "Force level = server injects reasoning_effort on every request",
    "刷新模型列表": "Refresh Models",
    "当前：强制档位（点击切换为跟随客户端）":
        "Now: forced level (click to follow client)",
    "当前：跟随客户端（点击切换为强制档位）":
        "Now: follow client (click to force level)",
    "模型": "Model",
    "状态": "Status",
    "思考档位": "Thinking Level",
    "上下文": "Context",
    "输入 ¥/M": "Input ¥/M",
    "输出 ¥/M": "Output ¥/M",
    "今日调用": "Calls Today",
    "今日费用": "Cost Today",
    "可用": "Available",
    "已下线": "Retired",
    "默认（后端）": "Default (backend)",
    "档位仅对支持 reasoning_effort 的模型生效（GLM / DeepSeek / Qwen）；“默认”表示不注入参数、由后端决定。平台模型可能随时增删，下线模型保留价格规则。":
        "Levels only apply to models supporting reasoning_effort (GLM / DeepSeek / Qwen); "
        "\"Default\" injects nothing and lets the backend decide. Platform models may "
        "change anytime; retired models keep their pricing rules.",
    # API 密钥
    "本地签发，客户端用任意 key 调用本代理；费用按 key 分别统计（仅统计，不限额）":
        "Issued locally; clients call the proxy with any key; costs tracked per key (stats only, no limits)",
    "＋ 新建密钥": "＋ New Key",
    "名称": "Name",
    "密钥": "Key",
    "创建时间": "Created",
    "请求数": "Requests",
    "输入 Tokens": "Input Tokens",
    "输出 Tokens": "Output Tokens",
    "费用": "Cost",
    "累计费用": "Total Cost",
    "操作": "Actions",
    "吊销": "Revoke",
    "新建 API 密钥": "New API Key",
    "名称（用于区分用途，如 zcode-main）":
        "Name (to tell purposes apart, e.g. zcode-main)",
    "生成密钥": "Generate Key",
    "取消": "Cancel",
    "密钥已生成": "Key Generated",
    "密钥只完整显示这一次，请立即复制保存。":
        "The full key is shown only once — copy and save it now.",
    # 用量明细
    "按 API key × 模型 汇总的 token 用量与费用（人民币）":
        "Token usage & cost aggregated by API key × model (CNY)",
    "导出 CSV": "Export CSV",
    "全部 Key": "All Keys",
    "全部模型": "All Models",
    "全部": "All",
    "今天": "Today",
    "近 7 天": "Last 7 days",
    "近 30 天": "Last 30 days",
    "导出完成": "Export Complete",
    "（未设价）": "(price not set)",
    "（无 key）": "(no key)",
    # 设置
    "设置 · 价格表与登录": "Settings · Pricing & Login",
    "所有价格由你手动输入（¥ / 百万 tokens）；未填写的模型只统计 tokens 不计费":
        "All prices are entered by you (¥ / million tokens); models without a price only track tokens",
    "UI 配色风格": "UI Color Theme",
    "切换立即生效并记住": "Applies instantly and is remembered",
    "界面语言": "Language",
    "重启程序后生效": "Takes effect after restart",
    "字体颜色": "Text Color",
    "黑色": "Black",
    "白色": "White",
    "背景图片（JPEG，铺满界面）": "Background Image (JPEG, fills the UI)",
    "选择 JPEG 图片…": "Choose JPEG…",
    "清除背景图": "Clear Background",
    "背景图会铺满整个界面并叠加半透明遮罩以保证文字可读":
        "The image fills the UI with a translucent overlay to keep text readable",
    "美元汇率（参考价换算用）": "USD Rate (for reference prices)",
    "输入价": "Input Price",
    "缓存命中价": "Cached Price",
    "输出价": "Output Price",
    "备注（来源）": "Note (source)",
    "未设置": "Not set",
    "清空": "Clear",
    "＋ 添加自定义模型": "＋ Add Custom Model",
    "恢复官方参考价": "Apply Reference Prices",
    "保存价格表": "Save Price Table",
    "通用设置": "General",
    "后端地址": "Backend URL",
    "端口": "Port",
    "档位虚拟模型（逗号分隔）": "Level-variant models (comma separated)",
    "保存并生效": "Save & Apply",
    "重新登录（打开浏览器）": "Sign In Again (opens browser)",
    "已保存": "Saved",
    "价格表已保存，立即对新请求生效。":
        "Price table saved; applies to new requests immediately.",
    "设置已保存。后端地址/端口变更需重启程序生效。":
        "Settings saved. Backend/port changes need a restart.",
    "添加自定义模型": "Add Custom Model",
    "模型 id（与后端模型列表一致）": "Model id (must match the backend list)",
    "添加": "Add",
    "登录成功，token 已验证有效。": "Signed in; token verified.",
    "正在打开浏览器等待登录…": "Opening browser, waiting for sign-in…",
    # 状态
    "● 后端已连接": "● Backend connected",
    "● 未登录": "● Not signed in",
    "● 凭证失效": "● Credentials invalid",
    "● 后端不可达": "● Backend unreachable",
    "● 启动中…": "● Starting…",
    # 吊销确认
    "确定吊销「{name}」？使用该 key 的客户端将立即 401。":
        "Revoke \"{name}\"? Clients using this key get 401 immediately.",
    # 状态文本（使用处包 T）
    "● 后端已连接": "● backend connected",
    "● 未登录": "● not signed in",
    "● 凭证失效": "● credentials expired",
    "● 后端不可达": "● backend unreachable",
    "● 启动中…": "● starting…",
    "默认（后端）": "Default (backend)",
    "—（未设价）": "— (no price)",
    "不是有效的 JPEG 文件（仅支持 JPEG 格式）": "Not a valid JPEG file (JPEG only)",
    # 背景图框选
    "背景图片（JPEG，框选区域）": "Background (JPEG, frame a region)",
    "选择背景图片": "Pick Background Image",
    "背景图片": "Background Image",
    "重新框选区域": "Re-frame Region",
    "框选背景显示区域": "Frame Background Region",
    "在图片上按住鼠标拖拽，圈选要做背景的区域":
        "Drag on the image to select the area to use as background",
    "使用所选区域": "Use Selected Area",
    "使用整张图片": "Use Full Image",
    "请先选择一张 JPEG 图片": "Please pick a JPEG image first",
    "选好图片后在弹窗里拖拽框选要显示的区域，背景会铺满界面并叠加半透明遮罩保证文字可读":
        "After picking an image, drag in the dialog to frame the region to show; "
        "the background fills the window with a translucent mask to keep text readable",
    # 配色主题名（kv 存中文名，显示走 T()）
    "深色（默认）": "Dark (default)",
    "浅色": "Light",
    "石墨灰": "Graphite",
    "深海蓝": "Deep Sea Blue",
    "玫瑰红": "Rose",
    "森林绿": "Forest Green",
    "琥珀橙": "Amber Orange",
    "暗夜紫": "Midnight Purple",
}


def T(s: str) -> str:
    """按当前语言翻译。英文缺失时回退中文原文。"""
    if LANG == "zh":
        return s
    return STRINGS.get(s, s)


def _fmt_tokens(n):
    n = n or 0
    if n >= 1_000_000:
        return f"{n/1e6:.2f}M"
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


def fmt_delta(diff: float) -> str:
    arrow = "↑" if diff >= 0 else "↓"
    if LANG == "zh":
        return f"{arrow} 较昨日 {abs(diff):.2f}"
    return f"{arrow} vs yesterday {abs(diff):.2f}"


def fmt_io(prompt: int, completion: int) -> str:
    if LANG == "zh":
        return f"输入 {_fmt_tokens(prompt)} · 输出 {_fmt_tokens(completion)}"
    return f"in {_fmt_tokens(prompt)} · out {_fmt_tokens(completion)}"


def fmt_cache_pct(pct: str) -> str:
    if LANG == "zh":
        return f"占输入 {pct}"
    return f"{pct} of input"


def fmt_fail(n: int) -> str:
    if LANG == "zh":
        return f"失败 {n}"
    return f"{n} failed"


def fmt_total_reqs(n: int) -> str:
    if LANG == "zh":
        return f"共 {n} 次请求"
    return f"{n} requests in total"
