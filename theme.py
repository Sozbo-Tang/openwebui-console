#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""theme.py — 参数化 QSS 主题系统。THEMES: 名称 → QSS。"""


def build_qss(bg="#1e1e22", panel="#232328", card="#26262c", border="#313136",
              table="#242429", table_alt="#27272d", head="#28282e",
              text="#e8e8ed", muted="#8a8a92", faint="#5a5a62",
              accent="#5b45b0", accent_hover="#6a52c4", focus="#7b5ce0",
              ok="#7bd88f", warn="#f5bd60", bad="#f2777a", info="#6db3f2",
              input_bg="#1e1e24", input_border="#3a3a44",
              nav_hover="#2a2a30", nav_active="#3b2f63"):
    return f"""
* {{ font-family: -apple-system, 'PingFang SC', 'Helvetica Neue', sans-serif;
    font-size: 13px; color: {text}; }}
QMainWindow, QWidget {{ background: {bg}; }}
QToolTip {{ background: {panel}; color: {text}; border: 1px solid {border}; }}

#Sidebar QListWidget {{ background: transparent; border: none; outline: none; }}
#Sidebar QListWidget::item {{ color: {muted}; padding: 10px 14px;
  border-radius: 8px; margin: 2px 8px; }}
#Sidebar QListWidget::item:selected {{ background: {nav_active}; color: #ffffff; }}
#Sidebar QListWidget::item:hover:!selected {{ background: {nav_hover}; }}
#StatusBox {{ color: {muted}; font-size: 11.5px; padding: 10px 14px;
  border-top: 1px solid {border}; }}

#PageTitle {{ font-size: 17px; font-weight: 600; }}
#PageSub {{ color: {muted}; font-size: 12px; }}
#SectionTitle {{ color: {text}; font-size: 13px; font-weight: 600; }}

#StatCard {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}
#StatCard QLabel[kind="k"] {{ color: {muted}; font-size: 12px; background: transparent; }}
#StatCard QLabel[kind="v"] {{ font-size: 22px; font-weight: 700; background: transparent; }}
#StatCard QLabel[kind="d"] {{ color: {ok}; font-size: 11.5px; background: transparent; }}

#StatePanel {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}
#StatePanel QLabel {{ background: transparent; }}

QTableWidget, QTableView {{ background: {table};
  alternate-background-color: {table_alt}; border: 1px solid {border};
  border-radius: 10px; gridline-color: {border};
  selection-background-color: {nav_active}; selection-color: #ffffff; }}
QHeaderView::section {{ background: {head}; color: {muted}; border: none;
  border-bottom: 1px solid {border}; padding: 7px 10px; font-size: 11.5px; }}
QTableCornerButton::section {{ background: {head}; border: none; }}

QPushButton {{ background: {accent}; color: #ffffff; border: none;
  border-radius: 8px; padding: 7px 16px; font-weight: 600; }}
QPushButton:hover {{ background: {accent_hover}; }}
QPushButton:disabled {{ background: {input_border}; color: {muted}; }}
QPushButton[ghost="true"] {{ background: {nav_hover}; color: {text}; font-weight: 500; }}
QPushButton[ghost="true"]:hover {{ background: {input_border}; }}
QPushButton[danger="true"] {{ background: {bad}; color: {bg}; font-weight: 500; }}
QPushButton[danger="true"]:hover {{ background: {bad}; }}

QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
  background: {input_bg}; border: 1px solid {input_border}; border-radius: 7px;
  padding: 6px 10px; selection-background-color: {accent}; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border-color: {focus}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {card}; border: 1px solid {input_border};
  selection-background-color: {nav_active}; }}

QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {input_border};
  border-radius: 4px; background: {input_bg}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}

#PillOk {{ color: {ok}; background: {card}; border: 1px solid {ok};
  border-radius: 9px; padding: 2px 10px; }}
#PillWarn {{ color: {warn}; background: {card}; border: 1px solid {warn};
  border-radius: 9px; padding: 2px 10px; }}
#PillBad {{ color: {bad}; background: {card}; border: 1px solid {bad};
  border-radius: 9px; padding: 2px 10px; }}
#PillInfo {{ color: {info}; background: {card}; border: 1px solid {info};
  border-radius: 9px; padding: 2px 10px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {input_border}; border-radius: 5px;
  min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {input_border}; border-radius: 5px;
  min-width: 30px; }}

QDialog {{ background: {panel}; }}
QLabel#DialogTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#DialogSub {{ color: {muted}; font-size: 12px; }}
"""


THEMES = {
    "深色（默认）": build_qss(),
    "浅色": build_qss(
        bg="#f2f2f6", panel="#ffffff", card="#ffffff", border="#d8d8e0",
        table="#ffffff", table_alt="#f7f7fa", head="#ececf2",
        text="#1c1c22", muted="#6a6a74", faint="#9a9aa4",
        accent="#5b45b0", accent_hover="#6a52c4", focus="#7b5ce0",
        ok="#1f7a3d", warn="#a06a00", bad="#c03540", info="#1f6ab0",
        input_bg="#ffffff", input_border="#c8c8d4",
        nav_hover="#e8e8ee", nav_active="#dcd6f5"),
    "石墨灰": build_qss(
        bg="#26262a", panel="#2c2c31", card="#303035", border="#3a3a40",
        table="#2e2e33", table_alt="#323237", head="#34343a",
        text="#e0e0e4", muted="#8e8e96", faint="#5e5e66",
        accent="#4a6a8a", accent_hover="#5a7aa0", focus="#6a8ab0",
        input_bg="#2a2a2f", input_border="#44444c",
        nav_hover="#34343a", nav_active="#3d5a78"),
    "深海蓝": build_qss(
        bg="#141c28", panel="#182230", card="#1d2838", border="#243448",
        table="#182230", table_alt="#1c2735", head="#203042",
        text="#dce8f4", muted="#7a94ac", faint="#4a647c",
        accent="#2a6a9a", accent_hover="#3a7aba", focus="#4a8ad0",
        ok="#5ad8a0", warn="#f0c060", bad="#f07070", info="#60b0f0",
        input_bg="#16202e", input_border="#2c4058",
        nav_hover="#1e2c3e", nav_active="#28527a"),
}

DEFAULT_THEME = "深色（默认）"


def names():
    return list(THEMES)


def get(name: str) -> str:
    return THEMES.get(name, THEMES[DEFAULT_THEME])
