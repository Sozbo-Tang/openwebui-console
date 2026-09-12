#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ui.py — PySide6 主窗口：侧边栏 + 仪表盘/模型档位/API密钥/用量明细/设置。
支持：8 套配色主题、字体颜色（黑/白）、界面语言（正统中文/English）、JPEG 背景图。"""
import csv
import os

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QListWidget, QStackedWidget, QFrame, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QDialog, QHeaderView,
    QAbstractItemView, QFileDialog, QMessageBox, QDoubleSpinBox,
)

import auth
import lang
import theme
from lang import T
from core import EFFORT_LEVELS, REFERENCE_PRICES_USD

STATE_TEXT = {
    "ok": ("● 后端已连接", "#7bd88f"),
    "no_creds": ("● 未登录", "#f5bd60"),
    "bad_creds": ("● 凭证失效", "#f2777a"),
    "backend_down": ("● 后端不可达", "#f2777a"),
    "starting": ("● 启动中…", "#f5bd60"),
}
LEVEL_LABELS = {"": T("默认（后端）"), "low": "low", "medium": "medium",
                "high": "high", "xhigh": "xhigh", "max": "max"}
LEVEL_ORDER = ["", "low", "medium", "high", "xhigh", "max"]


def fmt_money(v):
    if v is None:
        return "—"
    if abs(v) < 0.01 and v != 0:
        return f"¥{v:.4f}"
    return f"¥{v:.2f}"


def fmt_tokens(n):
    n = n or 0
    if n >= 1_000_000:
        return f"{n/1e6:.2f}M"
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


def pill(text, kind="g"):
    name = {"g": "PillOk", "o": "PillWarn", "r": "PillBad", "b": "PillInfo"}[kind]
    lab = QLabel(text)
    lab.setObjectName(name)
    lab.setAlignment(Qt.AlignCenter)
    return lab


class Bridge(QObject):
    """代理线程 → UI 线程的信号桥（Qt 信号跨线程发射是安全的）。"""
    requestLogged = Signal(dict)
    stateChanged = Signal(dict)


def stat_card(k_text, v_text, d_text=""):
    card = QFrame()
    card.setObjectName("StatCard")
    v = QVBoxLayout(card)
    v.setContentsMargins(16, 14, 16, 14)
    kl = QLabel(k_text); kl.setProperty("kind", "k")
    vl = QLabel(v_text); vl.setProperty("kind", "v")
    dl = QLabel(d_text or ""); dl.setProperty("kind", "d")
    v.addWidget(kl); v.addWidget(vl); v.addWidget(dl)
    card.value_label = vl
    card.delta_label = dl
    return card


def make_table(headers, stretch_cols=None):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch_cols:
        for c in stretch_cols:
            t.horizontalHeader().setSectionResizeMode(c, QHeaderView.Stretch)
    return t


def readonly_item(text, mono=False):
    it = QTableWidgetItem(str(text))
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def is_jpeg(path: str) -> bool:
    """校验文件确实是 JPEG（魔数 FFD8）。"""
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"\xff\xd8"
    except Exception:
        return False


# ================================================================ 仪表盘
class DashboardPage(QWidget):
    """今日用量卡片 + 后端连接状态面板。"""
    def __init__(self, store, proxy, parent=None):
        super().__init__(parent)
        self.store, self.proxy = store, proxy
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel(T("仪表盘")); title.setObjectName("PageTitle")
        sub = QLabel(T("今日用量与后端连接状态 · 实时更新"))
        sub.setObjectName("PageSub")
        root.addWidget(title); root.addWidget(sub)

        cards = QHBoxLayout(); cards.setSpacing(12)
        self.card_cost = stat_card(T("今日花费（人民币）"), "¥0.00")
        self.card_tok = stat_card(T("今日 Tokens"), "0")
        self.card_cache = stat_card(T("缓存命中"), "0")
        self.card_req = stat_card(T("今日请求"), "0")
        for c in (self.card_cost, self.card_tok, self.card_cache, self.card_req):
            cards.addWidget(c)
        root.addLayout(cards)

        panel = QFrame(); panel.setObjectName("StatePanel")
        pv = QVBoxLayout(panel); pv.setContentsMargins(18, 16, 18, 16); pv.setSpacing(7)
        self.state_label = QLabel()
        pv.addWidget(self.state_label)
        self.info_label = QLabel(); self.info_label.setObjectName("PageSub")
        pv.addWidget(self.info_label)
        self.detail_label = QLabel(); self.detail_label.setWordWrap(True)
        pv.addWidget(self.detail_label)
        root.addWidget(panel)
        root.addStretch(1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    def refresh(self):
        st = self.store.today_stats()
        self.update_cards(st)
        px = self.proxy
        state = px.state if px else "starting"
        detail = (px.state_detail or "") if px else ""
        text, color = STATE_TEXT.get(state, STATE_TEXT["starting"])
        self.state_label.setText(
            f"<span style='color:{color};font-size:15px;font-weight:700'>{T(text)}</span>")
        cache = px.models_cache.get("data") if px else None
        n_models = len(cache.get("data", [])) if cache else None
        url = px.store.get_kv("base_url") if px else "—"
        port = px.store.get_kv("port") if px else "—"
        self.info_label.setText(
            f"{T('后端')}　{url}　·　{T('监听')}　127.0.0.1:{port}　·　"
            f"{T('可用模型')}　{n_models if n_models is not None else '—'}")
        self.detail_label.setText(detail)
        self.detail_label.setStyleSheet(f"color:{color};font-size:12px;")
        self.detail_label.setVisible(bool(detail))

    def update_cards(self, st):
        self.card_cost.value_label.setText(fmt_money(st["cost"]))
        self.card_cost.delta_label.setText(lang.fmt_delta(st["cost"] - st["yesterday_cost"]))
        self.card_tok.value_label.setText(fmt_tokens(st["prompt"] + st["completion"]))
        self.card_tok.delta_label.setText(lang.fmt_io(st["prompt"], st["completion"]))
        self.card_cache.value_label.setText(fmt_tokens(st["cached"]))
        pct = f"{st['cached']/st['prompt']*100:.0f}%" if st["prompt"] else "—"
        self.card_cache.delta_label.setText(lang.fmt_cache_pct(pct))
        self.card_req.value_label.setText(f"{st['requests']:,}")
        self.card_req.delta_label.setText(lang.fmt_fail(st["fail"]))


# ================================================================ 模型与档位
class ModelsPage(QWidget):
    def __init__(self, store, proxy, parent=None):
        super().__init__(parent)
        self.store, self.proxy = store, proxy
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        head = QHBoxLayout(); head.setSpacing(10)
        title = QLabel(T("模型与思考档位")); title.setObjectName("PageTitle")
        head.addWidget(title)
        self.mode_btn = QPushButton()
        self.mode_btn.setCheckable(True)
        self.mode_btn.clicked.connect(self.toggle_mode)
        head.addWidget(self.mode_btn)
        hint = QLabel(T("强制档位 = 服务端注入 reasoning_effort，对所有请求生效"))
        hint.setObjectName("PageSub")
        head.addWidget(hint)
        head.addStretch(1)
        self.refresh_btn = QPushButton(T("刷新模型列表"))
        self.refresh_btn.setProperty("ghost", True)
        self.refresh_btn.clicked.connect(lambda: self.refresh(True))
        head.addWidget(self.refresh_btn)
        root.addLayout(head)

        self.table = make_table(
            [T("模型"), T("状态"), T("思考档位"), T("上下文"), T("输入 ¥/M"),
             T("输出 ¥/M"), T("今日调用"), T("今日费用")], stretch_cols=[0])
        root.addWidget(self.table, 1)

        note = QLabel(T("档位仅对支持 reasoning_effort 的模型生效（GLM / DeepSeek / Qwen）；"
                        "“默认”表示不注入参数、由后端决定。平台模型可能随时增删，"
                        "下线模型保留价格规则。"))
        note.setObjectName("PageSub")
        note.setWordWrap(True)
        root.addWidget(note)
        self.refresh()

    def toggle_mode(self):
        mode = "force" if self.mode_btn.isChecked() else "follow_client"
        self.store.set_kv("effort_mode", mode)
        self.refresh()

    def on_level_changed(self, model, level):
        self.store.set_level(model, level)

    def refresh(self, force_models=False):
        mode = self.store.get_kv("effort_mode")
        self.mode_btn.setText(T("当前：强制档位（点击切换为跟随客户端）") if mode == "force"
                              else T("当前：跟随客户端（点击切换为强制档位）"))
        self.mode_btn.setChecked(mode == "force")
        live = []
        models = self.proxy.list_models(force=force_models) if self.proxy else None
        if models:
            for m in models.get("data", []):
                mid = m.get("id", "")
                if "-" not in mid or mid.rsplit("-", 1)[1] not in EFFORT_LEVELS:
                    live.append(mid)
        prices = self.store.get_prices()
        all_ids = list(dict.fromkeys(live + [p for p in prices if p not in live]))
        stats = {m["m"]: m for m in self.store.model_stats_today()}
        self.table.setRowCount(0)
        for mid in all_ids:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, readonly_item(mid))
            is_live = mid in live
            self.table.setCellWidget(row, 1, pill(T("可用") if is_live else T("已下线"),
                                                  "g" if is_live else "o"))
            combo = QComboBox()
            for lv in LEVEL_ORDER:
                combo.addItem(LEVEL_LABELS[lv], lv)
            cur = self.store.get_level(mid) or ""
            combo.setCurrentIndex(LEVEL_ORDER.index(cur) if cur in LEVEL_ORDER else 0)
            combo.currentIndexChanged.connect(
                lambda i, m=mid, c=combo: self.on_level_changed(m, c.currentData()))
            self.table.setCellWidget(row, 2, combo)
            info = next((m for m in (models or {}).get("data", []) if m.get("id") == mid), None)
            ctx = info.get("max_model_len") if info else None
            self.table.setItem(row, 3, readonly_item(fmt_tokens(ctx) if ctx else "—"))
            p = prices.get(mid)
            self.table.setItem(row, 4, readonly_item(
                f"{p['input']:.2f}" if p and p["input"] is not None else T("未设置")))
            self.table.setItem(row, 5, readonly_item(
                f"{p['output']:.2f}" if p and p["output"] is not None else T("未设置")))
            s = stats.get(mid)
            self.table.setItem(row, 6, readonly_item(str(s["n"]) if s else "0"))
            self.table.setItem(row, 7, readonly_item(
                fmt_money(s["cost"]) if s and mid in prices else "—"))


# ================================================================ API 密钥
class KeysPage(QWidget):
    def __init__(self, store, proxy, parent=None):
        super().__init__(parent)
        self.store, self.proxy = store, proxy
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        head = QHBoxLayout()
        box = QVBoxLayout()
        box.addWidget(QLabel(T("API 密钥"), objectName="PageTitle"))
        sub = QLabel(T("本地签发，客户端用任意 key 调用本代理；费用按 key 分别统计（仅统计，不限额）"))
        sub.setObjectName("PageSub")
        box.addWidget(sub)
        head.addLayout(box)
        head.addStretch(1)
        btn = QPushButton(T("＋ 新建密钥"))
        btn.clicked.connect(self.create_key)
        head.addWidget(btn)
        root.addLayout(head)

        self.table = make_table(
            [T("名称"), T("密钥"), T("创建时间"), T("请求数"), T("输入 Tokens"),
             T("输出 Tokens"), T("费用"), T("累计费用"), T("操作")], stretch_cols=[1])
        root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        rows = self.store.list_keys()
        self.table.setRowCount(0)
        for k in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, readonly_item(k["name"]))
            self.table.setItem(row, 1, readonly_item(k["key"][:9] + "…" + k["key"][-4:]))
            self.table.setItem(row, 2, readonly_item(k["created_at"]))
            self.table.setItem(row, 3, readonly_item(str(k["today_requests"])))
            self.table.setItem(row, 4, readonly_item(fmt_tokens(k["today_prompt"])))
            self.table.setItem(row, 5, readonly_item(fmt_tokens(k["today_completion"])))
            self.table.setItem(row, 6, readonly_item(fmt_money(k["today_cost"])))
            self.table.setItem(row, 7, readonly_item(fmt_money(k["total_cost"])))
            btn = QPushButton(T("吊销"))
            btn.setProperty("danger", True)
            btn.clicked.connect(lambda _, kid=k["id"], nm=k["name"]: self.revoke(kid, nm))
            self.table.setCellWidget(row, 8, btn)

    def create_key(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(T("新建 API 密钥"))
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(T("名称（用于区分用途，如 zcode-main）")))
        name = QLineEdit(); v.addWidget(name)
        btns = QHBoxLayout()
        ok = QPushButton(T("生成密钥")); cancel = QPushButton(T("取消"))
        cancel.setProperty("ghost", True)
        btns.addStretch(1); btns.addWidget(cancel); btns.addWidget(ok)
        v.addLayout(btns)
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted or not name.text().strip():
            return
        k = self.store.create_key(name.text().strip())
        QMessageBox.information(
            self, T("密钥已生成"),
            f"{T('名称')}：{k['name']}\n\n{k['key']}\n\n{T('密钥只完整显示这一次，请立即复制保存。')}")
        self.refresh()

    def revoke(self, key_id, name):
        if QMessageBox.question(
                self, T("吊销"),
                T("确定吊销「{name}」？使用该 key 的客户端将立即 401。").format(name=name)) \
                == QMessageBox.Yes:
            self.store.revoke_key(key_id)
            self.refresh()


# ================================================================ 用量明细
class UsagePage(QWidget):
    """按 (API key × 模型) 聚合的 token 用量与费用。"""
    def __init__(self, store, proxy, parent=None):
        super().__init__(parent)
        self.store, self.proxy = store, proxy
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        head = QHBoxLayout(); head.setSpacing(10)
        box = QVBoxLayout()
        box.addWidget(QLabel(T("用量明细"), objectName="PageTitle"))
        sub = QLabel(T("按 API key × 模型 汇总的 token 用量与费用（人民币）"))
        sub.setObjectName("PageSub")
        box.addWidget(sub)
        head.addLayout(box)
        head.addStretch(1)
        export = QPushButton(T("导出 CSV")); export.setProperty("ghost", True)
        export.clicked.connect(self.export_csv)
        head.addWidget(export)
        root.addLayout(head)

        filters = QHBoxLayout(); filters.setSpacing(10)
        filters.addWidget(QLabel("API Key"))
        self.key_filter = QComboBox(); self.key_filter.setMinimumWidth(140)
        self.key_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.key_filter)
        filters.addWidget(QLabel(T("模型")))
        self.model_filter = QComboBox(); self.model_filter.setMinimumWidth(200)
        self.model_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.model_filter)
        filters.addStretch(1)
        root.addLayout(filters)

        self.table = make_table(
            ["API Key", T("模型"), T("请求数"), T("输入 Tokens"), T("缓存命中"),
             T("输出 Tokens"), T("费用")], stretch_cols=[0, 1])
        root.addWidget(self.table, 1)
        self.reload_filters()
        self.refresh()

    def reload_filters(self):
        for w in (self.key_filter, self.model_filter):
            w.blockSignals(True)
        self.key_filter.clear(); self.key_filter.addItem(T("全部 Key"), None)
        for k in self.store.list_keys():
            self.key_filter.addItem(k["name"], k["id"])
        self.model_filter.clear(); self.model_filter.addItem(T("全部模型"), None)
        for m in sorted(set(self.store.all_models_seen())):
            self.model_filter.addItem(m, m)
        for w in (self.key_filter, self.model_filter):
            w.blockSignals(False)

    def refresh(self):
        rows = self.store.usage_by_key_model(
            key_id=self.key_filter.currentData(),
            model=self.model_filter.currentData())
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cost = fmt_money(r["cost"]) if r["cost_known"] else "—（未设价）"
            vals = [r["key_name"], r["model"], str(r["requests"]),
                    fmt_tokens(r["prompt"]), fmt_tokens(r["cached"]),
                    fmt_tokens(r["completion"]), cost]
            for col, v in enumerate(vals):
                self.table.setItem(row, col, readonly_item(v, col in (3, 4, 5, 6)))

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, T("导出 CSV"), "usage.csv", "CSV (*.csv)")
        if not path:
            return
        rows = self.store.usage_by_key_model(
            key_id=self.key_filter.currentData(),
            model=self.model_filter.currentData())
        cols = ["key_name", "model", "requests", "prompt", "cached",
                "completion", "cost", "cost_known"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(cols)
            for r in rows:
                w.writerow([r.get(c, "") for c in cols])
        QMessageBox.information(self, T("导出完成"), path)


# ================================================================ 设置
class SettingsPage(QWidget):
    def __init__(self, store, proxy, on_style_change=None, parent=None):
        super().__init__(parent)
        self.store, self.proxy = store, proxy
        self.on_style_change = on_style_change
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(10)

        title = QLabel(T("设置 · 价格表与登录")); title.setObjectName("PageTitle")
        sub = QLabel(T("所有价格由你手动输入（¥ / 百万 tokens）；未填写的模型只统计 tokens 不计费"))
        sub.setObjectName("PageSub")
        root.addWidget(title); root.addWidget(sub)

        # ---- 界面：配色 / 语言 / 字体颜色 / 背景图 ----
        look = QHBoxLayout(); look.setSpacing(10)
        look.addWidget(QLabel(T("UI 配色风格")))
        self.theme_combo = QComboBox()
        for n in theme.names():
            self.theme_combo.addItem(n)
        self.theme_combo.setCurrentText(self.store.get_kv("ui_theme") or theme.DEFAULT_THEME)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        look.addWidget(self.theme_combo)
        look.addWidget(QLabel(T("界面语言")))
        self.lang_combo = QComboBox()
        for code in ("zh", "en"):
            self.lang_combo.addItem(lang.LANGUAGE_LABELS[code], code)
        cur_lang = self.store.get_kv("language") or "zh"
        self.lang_combo.setCurrentIndex(0 if cur_lang == "zh" else 1)
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        look.addWidget(self.lang_combo)
        look.addWidget(QLabel(T("字体颜色")))
        self.text_combo = QComboBox()
        self.text_combo.addItem(T("白色"), "white")
        self.text_combo.addItem(T("黑色"), "black")
        cur_tc = self.store.get_kv("text_color") or "white"
        self.text_combo.setCurrentIndex(0 if cur_tc == "white" else 1)
        self.text_combo.currentIndexChanged.connect(self.change_text_color)
        look.addWidget(self.text_combo)
        look.addStretch(1)
        root.addLayout(look)

        bg_row = QHBoxLayout(); bg_row.setSpacing(10)
        bg_row.addWidget(QLabel(T("背景图片（JPEG，铺满界面）")))
        self.bg_path = QLineEdit(self.store.get_kv("bg_image") or "")
        bg_row.addWidget(self.bg_path, 1)
        b_pick = QPushButton(T("选择 JPEG 图片…")); b_pick.setProperty("ghost", True)
        b_pick.clicked.connect(self.pick_bg)
        bg_row.addWidget(b_pick)
        b_clear = QPushButton(T("清除背景图")); b_clear.setProperty("ghost", True)
        b_clear.clicked.connect(self.clear_bg)
        bg_row.addWidget(b_clear)
        root.addLayout(bg_row)
        bg_hint = QLabel(T("背景图会铺满整个界面并叠加半透明遮罩以保证文字可读"))
        bg_hint.setObjectName("PageSub")
        root.addWidget(bg_hint)

        # ---- 价格表 ----
        self.price_table = QTableWidget(0, 6)
        self.price_table.setHorizontalHeaderLabels(
            [T("模型"), T("输入价"), T("缓存命中价"), T("输出价"),
             T("备注（来源）"), T("操作")])
        self.price_table.verticalHeader().setVisible(False)
        self.price_table.setAlternatingRowColors(True)
        self.price_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        root.addWidget(self.price_table, 1)

        row = QHBoxLayout(); row.setSpacing(10)
        row.addWidget(QLabel(T("美元汇率（参考价换算用）")))
        self.rate = QLineEdit(self.store.get_kv("exchange_rate"))
        self.rate.setFixedWidth(80)
        row.addWidget(self.rate)
        row.addStretch(1)
        b_add = QPushButton(T("＋ 添加自定义模型")); b_add.setProperty("ghost", True)
        b_add.clicked.connect(self.add_row)
        b_ref = QPushButton(T("恢复官方参考价")); b_ref.setProperty("ghost", True)
        b_ref.clicked.connect(self.apply_reference)
        b_save = QPushButton(T("保存价格表")); b_save.clicked.connect(self.save_prices)
        for b in (b_add, b_ref, b_save):
            row.addWidget(b)
        root.addLayout(row)

        root.addWidget(QLabel(T("通用设置"), objectName="SectionTitle"))
        gen = QHBoxLayout(); gen.setSpacing(10)
        gen.addWidget(QLabel(T("后端地址")))
        self.base_url = QLineEdit(self.store.get_kv("base_url")); gen.addWidget(self.base_url, 1)
        gen.addWidget(QLabel(T("端口")))
        self.port = QLineEdit(self.store.get_kv("port")); self.port.setFixedWidth(70)
        gen.addWidget(self.port)
        gen.addWidget(QLabel(T("档位虚拟模型（逗号分隔）")))
        self.base_models = QLineEdit(self.store.get_kv("effort_base_models"))
        gen.addWidget(self.base_models, 1)
        b_gen = QPushButton(T("保存并生效")); b_gen.setProperty("ghost", True)
        b_gen.clicked.connect(self.save_general)
        gen.addWidget(b_gen)
        root.addLayout(gen)

        login = QHBoxLayout(); login.setSpacing(10)
        self.login_state = QLabel(); self.login_state.setObjectName("PageSub")
        login.addWidget(self.login_state)
        login.addStretch(1)
        self.login_btn = QPushButton(T("重新登录（打开浏览器）"))
        self.login_btn.clicked.connect(self.relogin)
        login.addWidget(self.login_btn)
        root.addLayout(login)
        root.addStretch(1)

        self.load_prices()

    # ---------- 价格表（纯输入框，无上下调节按钮） ----------
    def _price_cell(self, value):
        w = QLineEdit("" if value is None else f"{value:g}")
        w.setPlaceholderText(T("未设置"))
        w.setAlignment(Qt.AlignRight)
        w.setFixedWidth(96)
        return w

    @staticmethod
    def _parse_price(w):
        t = w.text().strip()
        if not t:
            return None
        try:
            return float(t)
        except ValueError:
            return None

    def load_prices(self):
        prices = self.store.get_prices()
        models = set(prices) | set(self.store.all_models_seen())
        models |= live_set(self.proxy)
        self.price_table.setRowCount(0)
        for mid in sorted(models):
            self.append_price_row(mid, prices.get(mid))

    def append_price_row(self, model, p=None):
        row = self.price_table.rowCount()
        self.price_table.insertRow(row)
        self.price_table.setItem(row, 0, readonly_item(model))
        self.price_table.setCellWidget(row, 1, self._price_cell((p or {}).get("input")))
        self.price_table.setCellWidget(row, 2, self._price_cell((p or {}).get("cached")))
        self.price_table.setCellWidget(row, 3, self._price_cell((p or {}).get("output")))
        note = QLineEdit((p or {}).get("note") or "")
        self.price_table.setCellWidget(row, 4, note)
        btn = QPushButton(T("清空")); btn.setProperty("danger", True)
        btn.clicked.connect(lambda _, r=row: self.clear_row(r))
        self.price_table.setCellWidget(row, 5, btn)

    def add_row(self):
        dlg = QDialog(self); dlg.setWindowTitle(T("添加自定义模型"))
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(T("模型 id（与后端模型列表一致）")))
        name = QLineEdit(); v.addWidget(name)
        ok = QPushButton(T("添加")); ok.clicked.connect(dlg.accept)
        v.addWidget(ok)
        if dlg.exec() == QDialog.Accepted and name.text().strip():
            mid = name.text().strip()
            if not any(self.price_table.item(r, 0).text() == mid
                       for r in range(self.price_table.rowCount())):
                self.append_price_row(mid, None)

    def clear_row(self, row):
        for col in (1, 2, 3):
            self.price_table.cellWidget(row, col).setText("")

    def apply_reference(self):
        try:
            rate = float(self.rate.text() or "7.15")
        except ValueError:
            rate = 7.15
        for model, (i, ca, o, note) in REFERENCE_PRICES_USD.items():
            found = False
            for r in range(self.price_table.rowCount()):
                if self.price_table.item(r, 0).text() == model:
                    self.price_table.cellWidget(r, 1).setText(f"{round(i * rate, 4):g}")
                    if ca is not None:
                        self.price_table.cellWidget(r, 2).setText(f"{round(ca * rate, 4):g}")
                    self.price_table.cellWidget(r, 3).setText(f"{round(o * rate, 4):g}")
                    self.price_table.cellWidget(r, 4).setText(note)
                    found = True
                    break
            if not found:
                self.append_price_row(model, {"input": round(i * rate, 4),
                                              "cached": round(ca * rate, 4) if ca is not None else None,
                                              "output": round(o * rate, 4), "note": note})

    def save_prices(self):
        for r in range(self.price_table.rowCount()):
            model = self.price_table.item(r, 0).text()
            inp = self._parse_price(self.price_table.cellWidget(r, 1))
            ca = self._parse_price(self.price_table.cellWidget(r, 2))
            out = self._parse_price(self.price_table.cellWidget(r, 3))
            note = self.price_table.cellWidget(r, 4).text().strip()
            if inp is None and ca is None and out is None:
                self.store.delete_price(model)
            else:
                self.store.set_price(model, inp, ca, out, note)
        self.store.set_kv("exchange_rate", self.rate.text().strip() or "7.15")
        QMessageBox.information(self, T("已保存"), T("价格表已保存，立即对新请求生效。"))

    # ---------- 通用 ----------
    def save_general(self):
        self.store.set_kv("base_url", self.base_url.text().strip())
        try:
            self.store.set_kv("port", str(int(self.port.text().strip())))
        except ValueError:
            pass
        self.store.set_kv("effort_base_models", self.base_models.text().strip())
        QMessageBox.information(
            self, T("已保存"), T("设置已保存。后端地址/端口变更需重启程序生效。"))

    # ---------- 界面：主题 / 语言 / 字体 / 背景图 ----------
    def change_theme(self, name):
        self.store.set_kv("ui_theme", name)
        self._style()

    def change_text_color(self, i):
        self.store.set_kv("text_color", self.text_combo.currentData() or "white")
        self._style()

    def change_language(self, i):
        self.store.set_kv("language", self.lang_combo.currentData() or "zh")
        QMessageBox.information(self, T("已保存"), T("重启程序后生效"))

    def pick_bg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, T("背景图片（JPEG，铺满界面）"), "", "JPEG (*.jpg *.jpeg)")
        if not path:
            return
        if not is_jpeg(path):
            QMessageBox.warning(self, T("已保存"), "不是有效的 JPEG 文件（仅支持 JPEG 格式）")
            return
        self.store.set_kv("bg_image", path)
        self.bg_path.setText(path)
        self._style()

    def clear_bg(self):
        self.store.set_kv("bg_image", "")
        self.bg_path.setText("")
        self._style()

    def _style(self):
        if self.on_style_change:
            try:
                self.on_style_change()
            except Exception:
                pass

    def relogin(self):
        self.login_btn.setEnabled(False)
        self.login_state.setText(T("正在打开浏览器等待登录…"))
        def work():
            try:
                creds = auth.do_login(self.store.get_kv("base_url"))
                self.proxy.update_creds(creds)
                self.login_state.setText(T("登录成功，token 已验证有效。"))
            except Exception as e:
                self.login_state.setText(f"{T('登录失败')}：{e}")
            finally:
                self.login_btn.setEnabled(True)
        import threading
        threading.Thread(target=work, daemon=True).start()


def live_set(proxy):
    """当前在线的真实模型 id 集合。"""
    if not proxy:
        return set()
    ms = proxy.list_models()
    if not ms:
        return set()
    return {m.get("id") for m in ms.get("data", [])
            if "-" not in m.get("id", "") or m["id"].rsplit("-", 1)[1] not in EFFORT_LEVELS}


# ================================================================ 背景容器
class BgCentral(QWidget):
    """中央容器：JPEG 背景图铺满 + 主题色半透明遮罩；无图时纯主题底色。"""
    def __init__(self):
        super().__init__()
        self.pixmap = None
        self.mask_color = QColor("#1e1e22")

    def set_image(self, path):
        self.pixmap = QPixmap(path) if path and os.path.exists(path) else None

    def set_mask(self, hex_color: str):
        self.mask_color = QColor(hex_color)

    def paintEvent(self, ev):
        p = QPainter(self)
        if self.pixmap:
            scaled = self.pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding,
                                        Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
            m = QColor(self.mask_color); m.setAlpha(140)  # ~55% 遮罩
            p.fillRect(self.rect(), m)
        else:
            p.fillRect(self.rect(), self.mask_color)


# ================================================================ 主窗口
class MainWindow(QMainWindow):
    def __init__(self, store, proxy, bridge):
        super().__init__()
        self.store, self.proxy, self.bridge = store, proxy, bridge
        self.setWindowTitle(T("chat2api 控制台"))
        self.resize(1280, 820)

        self.central = BgCentral(); self.setCentralWidget(self.central)
        layout = QHBoxLayout(self.central)
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)

        sidebar = QWidget(); sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(190)
        sv = QVBoxLayout(sidebar); sv.setContentsMargins(0, 12, 0, 0); sv.setSpacing(2)
        brand = QLabel("  " + T("chat2api 控制台"))
        brand.setStyleSheet("font-size:14px;font-weight:700;padding:8px 14px 14px;")
        sv.addWidget(brand)
        self.nav = QListWidget()
        for icon, label in (("◧", T("仪表盘")), ("▤", T("模型与思考档位")),
                            ("⌘", T("API 密钥")), ("☰", T("用量明细")),
                            ("⚙", T("设置"))):
            self.nav.addItem(f"{icon}  {label}")
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self.switch_page)
        sv.addWidget(self.nav, 1)
        self.status_box = QLabel(); self.status_box.setObjectName("StatusBox")
        self.status_box.setWordWrap(True)
        sv.addWidget(self.status_box)
        layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.pages = [
            DashboardPage(store, proxy),
            ModelsPage(store, proxy),
            KeysPage(store, proxy),
            UsagePage(store, proxy),
            SettingsPage(store, proxy, on_style_change=self.apply_style),
        ]
        for pg in self.pages:
            self.stack.addWidget(pg)
        layout.addWidget(self.stack, 1)

        self.bridge.stateChanged.connect(self.update_status)
        self.update_status({"state": proxy.state, "detail": proxy.state_detail})
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(
            lambda: self.update_status({"state": self.proxy.state,
                                        "detail": self.proxy.state_detail}))
        self.status_timer.start(3000)
        self.apply_style()

    def apply_style(self):
        """统一入口：按 kv（主题/字体色/背景图）生成 QSS 并更新背景。"""
        name = self.store.get_kv("ui_theme") or theme.DEFAULT_THEME
        tc = self.store.get_kv("text_color") or ""
        bg = self.store.get_kv("bg_image") or ""
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.qss_for(name, tc, bg_image=bool(bg)))
        p = theme.palette(name)
        self.central.set_mask(p["bg"])
        self.central.set_image(bg)
        self.central.update()

    def switch_page(self, row):
        self.stack.setCurrentIndex(row)
        page = self.pages[row]
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except Exception:
                pass

    def update_status(self, s):
        text, color = STATE_TEXT.get(s.get("state", "starting"), STATE_TEXT["starting"])
        port = self.store.get_kv("port")
        detail = s.get("detail") or ""
        self.status_box.setText(
            f"<div style='color:{color};font-weight:600'>{T(text)}</div>"
            f"<div>{T('监听')} 127.0.0.1:{port}</div>"
            + (f"<div style='color:{color}'>{detail}</div>" if detail else ""))
