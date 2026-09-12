#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""theme.py — 深色主题 QSS（对应 demo 图配色）。"""

QSS = """
* { font-family: -apple-system, 'PingFang SC', 'Helvetica Neue', sans-serif;
    font-size: 13px; color: #e8e8ed; }
QMainWindow, QWidget { background: #1e1e22; }
QToolTip { background: #2a2a30; color: #e8e8ed; border: 1px solid #3a3a44; }

/* 侧边栏 */
#Sidebar { background: #232328; border-right: 1px solid #313136; min-width: 190px; max-width: 190px; }
#Sidebar QListWidget { background: transparent; border: none; outline: none; }
#Sidebar QListWidget::item { color: #b8b8c0; padding: 10px 14px; border-radius: 8px; margin: 2px 8px; }
#Sidebar QListWidget::item:selected { background: #3b2f63; color: #ffffff; }
#Sidebar QListWidget::item:hover:!selected { background: #2a2a30; }
#StatusBox { color: #8a8a92; font-size: 11.5px; padding: 10px 14px; border-top: 1px solid #313136; }

/* 页面骨架 */
#PageTitle { font-size: 17px; font-weight: 600; }
#PageSub { color: #8a8a92; font-size: 12px; }
#SectionTitle { color: #a8a8b0; font-size: 13px; font-weight: 600; }

/* 统计卡片 */
#StatCard { background: #26262c; border: 1px solid #313136; border-radius: 12px; }
#StatCard QLabel[kind="k"] { color: #8a8a92; font-size: 12px; background: transparent; }
#StatCard QLabel[kind="v"] { font-size: 22px; font-weight: 700; background: transparent; }
#StatCard QLabel[kind="d"] { color: #7bd88f; font-size: 11.5px; background: transparent; }

/* 表格 */
QTableWidget, QTableView { background: #242429; alternate-background-color: #27272d;
  border: 1px solid #313136; border-radius: 10px; gridline-color: #2c2c32;
  selection-background-color: #3b2f63; selection-color: #ffffff; }
QHeaderView::section { background: #28282e; color: #8a8a92; border: none;
  border-bottom: 1px solid #313136; padding: 7px 10px; font-size: 11.5px; }
QTableCornerButton::section { background: #28282e; border: none; }

/* 控件 */
QPushButton { background: #5b45b0; color: #fff; border: none; border-radius: 8px;
  padding: 7px 16px; font-weight: 600; }
QPushButton:hover { background: #6a52c4; }
QPushButton:disabled { background: #3a3a44; color: #77777f; }
QPushButton[ghost="true"] { background: #2f2f36; color: #c8c8d0; font-weight: 500; }
QPushButton[ghost="true"]:hover { background: #3a3a42; }
QPushButton[danger="true"] { background: #4a2a2e; color: #f2777a; font-weight: 500; }
QPushButton[danger="true"]:hover { background: #5c3339; }

QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
  background: #1e1e24; border: 1px solid #3a3a44; border-radius: 7px; padding: 6px 10px;
  selection-background-color: #5b45b0; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border-color: #7b5ce0; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #26262c; border: 1px solid #3a3a44;
  selection-background-color: #3b2f63; }

QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #4a4a55;
  border-radius: 4px; background: #1e1e24; }
QCheckBox::indicator:checked { background: #5b45b0; border-color: #5b45b0; }

/* 徽标样式由代码着色，这里给 QFrame 圆角 */
#PillOk { color: #7bd88f; background: #1d3325; border-radius: 9px; padding: 2px 9px; }
#PillWarn { color: #f5bd60; background: #3a2f1d; border-radius: 9px; padding: 2px 9px; }
#PillBad { color: #f2777a; background: #3a2224; border-radius: 9px; padding: 2px 9px; }
#PillInfo { color: #6db3f2; background: #1d2a3d; border-radius: 9px; padding: 2px 9px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #3a3a44; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4a4a55; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #3a3a44; border-radius: 5px; min-width: 30px; }

QDialog { background: #242429; }
QLabel#DialogTitle { font-size: 14px; font-weight: 600; }
QLabel#DialogSub { color: #8a8a92; font-size: 12px; }
"""
