#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""theme.py — 参数化 QSS 主题系统。
8 套配色调色板 + 字体颜色覆盖（黑/白）+ 背景图模式（容器透明化）。"""


def _hex(c: str, a: int) -> str:
    """'#rrggbb' → 'rgba(r,g,b,a)'，a 为 0-255 alpha。"""
    c = c.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


def build_qss(p: dict, card_alpha=None, table_alpha=None, input_alpha=None):
    """由调色板生成 QSS。alpha 参数用于背景图模式（None = 不透明）。"""
    ca = card_alpha if card_alpha is not None else 255
    ta = table_alpha if table_alpha is not None else 255
    ia = input_alpha if input_alpha is not None else 255
    card = _hex(p["card"], ca)
    table = _hex(p["table"], ta)
    table_alt = _hex(p["table_alt"], ta)
    input_bg = _hex(p["input_bg"], ia)
    return f"""
* {{ font-family: -apple-system, 'PingFang SC', 'Helvetica Neue', sans-serif;
    font-size: 13px; color: {p['text']}; }}
QMainWindow, QWidget {{ background: {p['bg']}; }}
QLabel {{ background: transparent; }}
QToolTip {{ background: {p['panel']}; color: {p['text']};
  border: 1px solid {p['border']}; }}

#Sidebar QListWidget {{ background: transparent; border: none; outline: none; }}
#Sidebar QListWidget::item {{ color: {p['muted']}; padding: 10px 14px;
  border-radius: 8px; margin: 2px 8px; }}
#Sidebar QListWidget::item:selected {{ background: {p['nav_active']}; color: #ffffff; }}
#Sidebar QListWidget::item:hover:!selected {{ background: {p['nav_hover']}; }}
#StatusBox {{ color: {p['muted']}; font-size: 11.5px; padding: 10px 14px;
  border-top: 1px solid {p['border']}; }}

#PageTitle {{ font-size: 17px; font-weight: 600; }}
#PageSub {{ color: {p['muted']}; font-size: 12px; }}
#SectionTitle {{ color: {p['text']}; font-size: 13px; font-weight: 600; }}

#StatCard {{ background: {card}; border: 1px solid {p['border']};
  border-radius: 12px; }}
#StatCard QLabel {{ background: transparent; }}
#StatCard QLabel[kind="k"] {{ color: {p['muted']}; font-size: 12px; }}
#StatCard QLabel[kind="v"] {{ font-size: 22px; font-weight: 700; }}
#StatCard QLabel[kind="d"] {{ color: {p['ok']}; font-size: 11.5px; }}

#StatePanel {{ background: {card}; border: 1px solid {p['border']};
  border-radius: 12px; }}
#StatePanel QLabel {{ background: transparent; }}

QTableWidget, QTableView {{ background: {table};
  alternate-background-color: {table_alt}; border: 1px solid {p['border']};
  border-radius: 10px; gridline-color: {p['border']};
  selection-background-color: {p['nav_active']}; selection-color: #ffffff; }}
QHeaderView::section {{ background: {p['head']}; color: {p['muted']}; border: none;
  border-bottom: 1px solid {p['border']}; padding: 7px 10px; font-size: 11.5px; }}
QTableCornerButton::section {{ background: {p['head']}; border: none; }}

QPushButton {{ background: {p['accent']}; color: #ffffff; border: none;
  border-radius: 8px; padding: 7px 16px; font-weight: 600; }}
QPushButton:hover {{ background: {p['accent_hover']}; }}
QPushButton:disabled {{ background: {p['input_border']}; color: {p['muted']}; }}
QPushButton[ghost="true"] {{ background: {p['nav_hover']}; color: {p['text']};
  font-weight: 500; }}
QPushButton[ghost="true"]:hover {{ background: {p['input_border']}; }}
QPushButton[danger="true"] {{ background: {p['bad']}; color: #ffffff;
  font-weight: 500; }}
QPushButton[danger="true"]:hover {{ background: {p['bad']}; }}

QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
  background: {input_bg}; border: 1px solid {p['input_border']}; border-radius: 7px;
  padding: 6px 10px; selection-background-color: {p['accent']}; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border-color: {p['focus']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {p['card']};
  border: 1px solid {p['input_border']}; selection-background-color: {p['nav_active']}; }}

QCheckBox::indicator {{ width: 15px; height: 15px;
  border: 1px solid {p['input_border']}; border-radius: 4px; background: {input_bg}; }}
QCheckBox::indicator:checked {{ background: {p['accent']};
  border-color: {p['accent']}; }}

#PillOk {{ color: {p['ok']}; background: {card}; border: 1px solid {p['ok']};
  border-radius: 9px; padding: 2px 10px; }}
#PillWarn {{ color: {p['warn']}; background: {card}; border: 1px solid {p['warn']};
  border-radius: 9px; padding: 2px 10px; }}
#PillBad {{ color: {p['bad']}; background: {card}; border: 1px solid {p['bad']};
  border-radius: 9px; padding: 2px 10px; }}
#PillInfo {{ color: {p['info']}; background: {card}; border: 1px solid {p['info']};
  border-radius: 9px; padding: 2px 10px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['input_border']}; border-radius: 5px;
  min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['input_border']};
  border-radius: 5px; min-width: 30px; }}

QDialog {{ background: {p['panel']}; }}
QLabel#DialogTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#DialogSub {{ color: {p['muted']}; font-size: 12px; }}
"""


# 调色板：名称 → 颜色集（bg 面板遮罩用、card 卡片、accent 强调…）
PALETTES = {
    "深色（默认）": dict(
        bg="#1e1e22", panel="#232328", card="#26262c", border="#313136",
        table="#242429", table_alt="#27272d", head="#28282e",
        text="#e8e8ed", muted="#8a8a92", faint="#5a5a62",
        accent="#5b45b0", accent_hover="#6a52c4", focus="#7b5ce0",
        ok="#7bd88f", warn="#f5bd60", bad="#f2777a", info="#6db3f2",
        input_bg="#1e1e24", input_border="#3a3a44",
        nav_hover="#2a2a30", nav_active="#3b2f63"),
    "浅色": dict(
        bg="#f2f2f6", panel="#ffffff", card="#ffffff", border="#d8d8e0",
        table="#ffffff", table_alt="#f7f7fa", head="#ececf2",
        text="#1c1c22", muted="#6a6a74", faint="#9a9aa4",
        accent="#5b45b0", accent_hover="#6a52c4", focus="#7b5ce0",
        ok="#1f7a3d", warn="#a06a00", bad="#c03540", info="#1f6ab0",
        input_bg="#ffffff", input_border="#c8c8d4",
        nav_hover="#e8e8ee", nav_active="#dcd6f5"),
    "石墨灰": dict(
        bg="#26262a", panel="#2c2c31", card="#303035", border="#3a3a40",
        table="#2e2e33", table_alt="#323237", head="#34343a",
        text="#e0e0e4", muted="#8e8e96", faint="#5e5e66",
        accent="#4a6a8a", accent_hover="#5a7aa0", focus="#6a8ab0",
        ok="#7bd88f", warn="#f5bd60", bad="#f2777a", info="#6db3f2",
        input_bg="#2a2a2f", input_border="#44444c",
        nav_hover="#34343a", nav_active="#3d5a78"),
    "深海蓝": dict(
        bg="#141c28", panel="#182230", card="#1d2838", border="#243448",
        table="#182230", table_alt="#1c2735", head="#203042",
        text="#dce8f4", muted="#7a94ac", faint="#4a647c",
        accent="#2a6a9a", accent_hover="#3a7aba", focus="#4a8ad0",
        ok="#5ad8a0", warn="#f0c060", bad="#f07070", info="#60b0f0",
        input_bg="#16202e", input_border="#2c4058",
        nav_hover="#1e2c3e", nav_active="#28527a"),
    "玫瑰红": dict(
        bg="#221a1e", panel="#282024", card="#2e2429", border="#3a2c32",
        table="#2a2126", table_alt="#2e252a", head="#342a2f",
        text="#f0e4e8", muted="#a08890", faint="#6a5a62",
        accent="#b04a6a", accent_hover="#c05a7a", focus="#d06a8a",
        ok="#7bd88f", warn="#f5bd60", bad="#f2777a", info="#e88ab0",
        input_bg="#282026", input_border="#463840",
        nav_hover="#342a2f", nav_active="#6a3a4e"),
    "森林绿": dict(
        bg="#161e18", panel="#1a241d", card="#1f2a22", border="#26352b",
        table="#1d271f", table_alt="#212c24", head="#263328",
        text="#e2eee6", muted="#88a092", faint="#5a7264",
        accent="#3a8a5a", accent_hover="#4a9a6a", focus="#5aaa7a",
        ok="#7bd88f", warn="#f5bd60", bad="#f2777a", info="#8ac8a8",
        input_bg="#1c261f", input_border="#38483e",
        nav_hover="#243028", nav_active="#2e5a3e"),
    "琥珀橙": dict(
        bg="#221c14", panel="#282218", card="#2e281c", border="#3a3222",
        table="#2a241a", table_alt="#2e281e", head="#342e20",
        text="#f2ead9", muted="#a89a80", faint="#6e6450",
        accent="#b0782a", accent_hover="#c0883a", focus="#d0984a",
        ok="#8ad878", warn="#f5c860", bad="#f28860", info="#e8b070",
        input_bg="#282218", input_border="#484030",
        nav_hover="#2e2820", nav_active="#5e4a28"),
    "暗夜紫": dict(
        bg="#1a1424", panel="#201a2c", card="#262034", border="#2e263e",
        table="#221c30", table_alt="#262035", head="#2c2440",
        text="#e8e2f2", muted="#9488aa", faint="#645a78",
        accent="#6a4a9a", accent_hover="#7a5aaa", focus="#8a6aba",
        ok="#8ad8a0", warn="#f0c070", bad="#f08090", info="#a890e0",
        input_bg="#201a2c", input_border="#3c3450",
        nav_hover="#262038", nav_active="#40305e"),
}

DEFAULT_THEME = "深色（默认）"

# 字体颜色覆盖：black/white → 正文与次级色的固定取值
TEXT_OVERRIDES = {
    "black": dict(text="#16161c", muted="#4e4e58", faint="#8a8a94"),
    "white": dict(text="#f2f2f6", muted="#a8a8b0", faint="#6a6a74"),
}


def names() -> list:
    return list(PALETTES)


def palette(name: str) -> dict:
    return dict(PALETTES.get(name, PALETTES[DEFAULT_THEME]))


def qss_for(name: str, text_color: str = "", bg_image: bool = False) -> str:
    """生成指定主题的 QSS。
    text_color: ''=跟随主题 / 'black' / 'white'（覆盖正文与次级文字色）
    bg_image: True 时容器透明化（配合主窗口 paintEvent 绘制背景图 + 遮罩）"""
    p = palette(name)
    if text_color in TEXT_OVERRIDES:
        p.update(TEXT_OVERRIDES[text_color])
    if bg_image:
        # 遮罩承担主要可读性（paint 时画 bg 色 ~55% alpha）；
        # 卡片 72%、表格 90%、输入框 90% —— 边缘和空隙透出背景图。
        # 关键：页面容器/堆栈/侧边栏必须透明，否则它们画不透明主题色把背景图盖住。
        qss = build_qss(p, card_alpha=184, table_alpha=230, input_alpha=230)
        qss += """
QStackedWidget { background: transparent; }
QWidget#PageRoot { background: transparent; }
QWidget#Sidebar { background: transparent; }
"""
        return qss
    return build_qss(p)
