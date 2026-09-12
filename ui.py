#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ui.py — PySide6 主窗口：侧边栏 + 仪表盘/模型档位/API密钥/用量明细/设置(价格表)。"""
import csv
import os

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QDate
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QStackedWidget, QFrame, QTableWidget,
    QTableWidgetItem, QPushButton, QLineEdit, QComboBox, QDialog,
    QVBoxLayout as DV, QHBoxLayout as DH, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox, QDateEdit, QDoubleSpinBox, QCheckBox, QSizePolicy,
)

import auth
import theme
from core import EFFORT_LEVELS, REFERENCE_PRICES_USD, today_str

STATE_TEXT = {
    "ok": ("● 后端已连接", "#7bd88f"),
    "no_creds": ("● 未登录", "#f5bd60"),
    "bad_creds": ("● 凭证失效", "#f2777a"),
    "backend_down": ("● 后端不可达", "#f2777a"),
    "starting": ("● 启动中…", "#f5bd60"),
}
LEVEL_LABELS = {"": "默认（后端）", "low": "low", "medium": "medium",
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
    """代理线程 → UI 线程的信号桥（Qt 信号跨线程安全）。"""
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
    t.setShowGrid(False)
    t.setWordWrap(False)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch_cols:
        for c in stretch_cols:
            h.setSectionResizeMode(c, QHeaderView.Stretch)
    return t


def readonly_item(text, mono=False):
    it = QTableWidgetItem(str(text))
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    if mono:
        from PySide6.QtGui import QFont
        f = QFont("Menlo")
        f.setPointSize(11)
        it.setFont(f)
    return it


# ================================================================ 仪表盘
class DashboardPage(QWidget):
    """今日用量卡片 + 后端连接状态面板。"""
    def __init__(self, store, proxy, parent=None):
        super().__init__(parent)
        self.store, self.proxy = store, proxy
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("仪表盘"); title.setObjectName("PageTitle")
        sub = QLabel("今日用量与后端连接状态 · 实时更新")
        sub.setObjectName("PageSub")
        root.addWidget(title); root.addWidget(sub)

        cards = QHBoxLayout(); cards.setSpacing(12)
        self.card_cost = stat_card("今日花费（人民币）", "¥0.00")
        self.card_tok = stat_card("今日 Tokens", "0")
        self.card_cache = stat_card("缓存命中", "0")
        self.card_req = stat_card("今日请求", "0")
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
            f"<span style='color:{color};font-size:15px;font-weight:700'>{text}</span>")
        cache = (px.models_cache.get("data") if px else None)
        n_models = len(cache.get("data", [])) if cache else None
        url = px.store.get_kv("base_url") if px else "—"
        port = px.store.get_kv("port") if px else "—"
        self.info_label.setText(
            f"后端　{url}　·　监听　127.0.0.1:{port}　·　"
            f"可用模型　{n_models if n_models is not None else '—'}")
        self.detail_label.setText(detail)
        self.detail_label.setStyleSheet(
            f"color:{color};font-size:12px;")
        self.detail_label.setVisible(bool(detail))

    def update_cards(self, st):
        self.card_cost.value_label.setText(fmt_money(st["cost"]))
        diff = st["cost"] - st["yesterday_cost"]
        arrow = "↑" if diff >= 0 else "↓"
        self.card_cost.delta_label.setText(f"{arrow} 较昨日 {abs(diff):.2f}")
        self.card_tok.value_label.setText(fmt_tokens(st["prompt"] + st["completion"]))
        self.card_tok.delta_label.setText(
            f"输入 {fmt_tokens(st['prompt'])} · 输出 {fmt_tokens(st['completion'])}")
        self.card_cache.value_label.setText(fmt_tokens(st["cached"]))
        pct = f"{st['cached']/st['prompt']*100:.0f}%" if st["prompt"] else "—"
        self.card_cache.delta_label.setText(f"占输入 {pct}")
        self.card_req.value_label.setText(f"{st['requests']:,}")
        self.card_req.delta_label.setText(f"失败 {st['fail']}")


# ================================================================ 模型与档位
class ModelsPage(QWidget):
    def __init__(self, store, proxy, parent=None):
        super().__init__(parent)
        self.store, self.proxy = store, proxy
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        head = DH(); head.setSpacing(10)
        title = QLabel("模型与思考档位"); title.setObjectName("PageTitle")
        head.addWidget(title)
        self.mode_btn = QPushButton()
        self.mode_btn.setCheckable(True)
        self.mode_btn.clicked.connect(self.toggle_mode)
        head.addWidget(self.mode_btn)
        hint = QLabel("强制档位 = 服务端注入 reasoning_effort，对所有请求生效")
        hint.setObjectName("PageSub")
        head.addWidget(hint)
        head.addStretch(1)
        self.refresh_btn = QPushButton("刷新模型列表")
        self.refresh_btn.setProperty("ghost", True)
        self.refresh_btn.clicked.connect(lambda: self.refresh(True))
        head.addWidget(self.refresh_btn)
        root.addLayout(head)

        self.table = make_table(
            ["模型", "状态", "思考档位", "上下文", "输入 ¥/M", "输出 ¥/M",
             "今日调用", "今日费用"], stretch_cols=[0])
        root.addWidget(self.table, 1)

        note = QLabel("档位仅对支持 reasoning_effort 的模型生效（GLM / DeepSeek / Qwen）；"
                      "“默认”表示不注入参数、由后端决定。平台模型可能随时增删，"
                      "下线模型保留价格规则。")
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
        self.mode_btn.setText("当前：强制档位（点击切换为跟随客户端）" if mode == "force"
                              else "当前：跟随客户端（点击切换为强制档位）")
        self.mode_btn.setChecked(mode == "force")
        # 合并：后端在线模型 + 出现过/已设价模型
        live = []
        models = self.proxy.list_models(force=force_models) if self.proxy else None
        if models:
            for m in models.get("data", []):
                mid = m.get("id", "")
                if "-" not in mid or mid.rsplit("-", 1)[1] not in EFFORT_LEVELS:
                    live.append(mid)
        seen = set(self.store.all_models_seen())
        prices = self.store.get_prices()
        all_ids = list(dict.fromkeys(live + [p for p in prices if p not in live]))
        levels = self.store.all_levels()
        stats = {m["m"]: m for m in self.store.model_stats_today()}
        self.table.setRowCount(0)
        for mid in all_ids:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, readonly_item(mid))
            is_live = mid in live
            self.table.setCellWidget(row, 1, pill("可用" if is_live else "已下线",
                                                  "g" if is_live else "o"))
            # 档位选择器
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
            self.table.setItem(row, 4, readonly_item(f"{p['input']:.2f}" if p and p["input"] is not None else "未设置"))
            self.table.setItem(row, 5, readonly_item(f"{p['output']:.2f}" if p and p["output"] is not None else "未设置"))
            s = stats.get(mid)
            self.table.setItem(row, 6, readonly_item(str(s["n"]) if s else "0"))
            self.table.setItem(row, 7, readonly_item(fmt_money(s["cost"]) if s and mid in prices else "—"))


# ================================================================ API 密钥
class KeysPage(QWidget):
    def __init__(self, store, proxy, parent=None):
        super().__init__(parent)
        self.store, self.proxy = store, proxy
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        head = DH()
        box = DV()
        box.addWidget(QLabel("API 密钥", objectName="PageTitle"))
        sub = QLabel("本地签发，客户端用任意 key 调用本代理；费用按 key 分别统计（仅统计，不限额）")
        sub.setObjectName("PageSub")
        box.addWidget(sub)
        head.addLayout(box)
        head.addStretch(1)
        btn = QPushButton("＋ 新建密钥")
        btn.clicked.connect(self.create_key)
        head.addWidget(btn)
        root.addLayout(head)

        self.table = make_table(
            ["名称", "密钥", "创建时间", "今日请求", "今日 Tokens", "今日费用",
             "累计费用", "操作"], stretch_cols=[1])
        root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        rows = self.store.list_keys()
        self.table.setRowCount(0)
        for k in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, readonly_item(k["name"]))
            self.table.setItem(row, 1, readonly_item(k["key"][:9] + "…" + k["key"][-4:], mono=True))
            self.table.setItem(row, 2, readonly_item(k["created_at"]))
            self.table.setItem(row, 3, readonly_item(str(k["today_requests"])))
            self.table.setItem(row, 4, readonly_item(fmt_tokens(k["today_prompt"] + k["today_completion"])))
            self.table.setItem(row, 5, readonly_item(fmt_money(k["today_cost"])))
            self.table.setItem(row, 6, readonly_item(fmt_money(k["total_cost"])))
            btn = QPushButton("吊销")
            btn.setProperty("danger", True)
            btn.clicked.connect(lambda _, kid=k["id"], nm=k["name"]: self.revoke(kid, nm))
            self.table.setCellWidget(row, 7, btn)

    def create_key(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("新建 API 密钥")
        v = DV(dlg)
        v.addWidget(QLabel("名称（用于区分用途，如 zcode-main）"))
        name = QLineEdit(); v.addWidget(name)
        btns = DH()
        ok = QPushButton("生成密钥"); cancel = QPushButton("取消")
        cancel.setProperty("ghost", True)
        btns.addStretch(1); btns.addWidget(cancel); btns.addWidget(ok)
        v.addLayout(btns)
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted or not name.text().strip():
            return
        k = self.store.create_key(name.text().strip())
        QMessageBox.information(
            self, "密钥已生成",
            f"名称：{k['name']}\n\n{k['key']}\n\n密钥只完整显示这一次，请立即复制保存。")
        self.refresh()

    def revoke(self, key_id, name):
        if QMessageBox.question(self, "吊销密钥",
                                f"确定吊销「{name}」？使用该 key 的客户端将立即 401。") \
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

        head = DH(); head.setSpacing(10)
        box = DV()
        box.addWidget(QLabel("用量明细", objectName="PageTitle"))
        sub = QLabel("按 API key × 模型 汇总的 token 用量与费用（人民币）")
        sub.setObjectName("PageSub")
        box.addWidget(sub)
        head.addLayout(box)
        head.addStretch(1)
        export = QPushButton("导出 CSV"); export.setProperty("ghost", True)
        export.clicked.connect(self.export_csv)
        head.addWidget(export)
        root.addLayout(head)

        filters = DH(); filters.setSpacing(10)
        filters.addWidget(QLabel("API Key"))
        self.key_filter = QComboBox(); self.key_filter.setMinimumWidth(140)
        self.key_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.key_filter)
        filters.addWidget(QLabel("模型"))
        self.model_filter = QComboBox(); self.model_filter.setMinimumWidth(200)
        self.model_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.model_filter)
        filters.addStretch(1)
        root.addLayout(filters)

        self.table = make_table(
            ["API Key", "模型", "请求数", "输入 Tokens", "缓存命中", "输出 Tokens",
             "费用"], stretch_cols=[0, 1])
        root.addWidget(self.table, 1)
        self.reload_filters()
        self.refresh()

    def reload_filters(self):
        for w in (self.key_filter, self.model_filter):
            w.blockSignals(True)
        self.key_filter.clear(); self.key_filter.addItem("全部 Key", None)
        for k in self.store.list_keys():
            self.key_filter.addItem(k["name"], k["id"])
        self.model_filter.clear(); self.model_filter.addItem("全部模型", None)
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
        path, _ = QFileDialog.getSaveFileName(self, "导出用量汇总", "usage.csv", "CSV (*.csv)")
        if not path:
            return
        rows = self.store.usage_by_key_model(
            key_id=self.key_filter.currentData(),
            model=self.model_filter.currentData())
        cols = ["key_name", "model", "requests", "prompt", "cached",
                "completion", "reasoning", "cost", "cost_known", "fails"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(cols)
            for r in rows:
                w.writerow([r.get(c, "") for c in cols])
        QMessageBox.information(self, "导出完成", f"已导出 {len(rows)} 行到\n{path}")


# ================================================================ 设置（价格表 + 通用）
class SettingsPage(QWidget):
    def __init__(self, store, proxy, parent=None):
        super().__init__(parent)
        self.store, self.proxy = store, proxy
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(10)

        title = QLabel("设置 · 价格表与登录"); title.setObjectName("PageTitle")
        sub = QLabel("所有价格由你手动输入（¥ / 百万 tokens）；未填写的模型只统计 tokens 不计费")
        sub.setObjectName("PageSub")
        root.addWidget(title); root.addWidget(sub)

        theme_row = QHBoxLayout(); theme_row.setSpacing(10)
        theme_row.addWidget(QLabel("UI 配色风格"))
        self.theme_combo = QComboBox()
        for n in theme.names():
            self.theme_combo.addItem(n)
        self.theme_combo.setCurrentText(
            self.store.get_kv("ui_theme") or theme.DEFAULT_THEME)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        theme_row.addWidget(self.theme_combo)
        hint = QLabel("切换立即生效并记住")
        hint.setObjectName("PageSub")
        theme_row.addWidget(hint)
        theme_row.addStretch(1)
        root.addLayout(theme_row)

        self.price_table = QTableWidget(0, 6)
        self.price_table.setHorizontalHeaderLabels(
            ["模型", "输入价", "缓存命中价", "输出价", "备注（来源）", "操作"])
        self.price_table.verticalHeader().setVisible(False)
        self.price_table.setAlternatingRowColors(True)
        self.price_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        root.addWidget(self.price_table, 1)

        row = DH(); row.setSpacing(10)
        row.addWidget(QLabel("美元汇率（参考价换算用）"))
        self.rate = QLineEdit(self.store.get_kv("exchange_rate"))
        self.rate.setFixedWidth(80)
        row.addWidget(self.rate)
        row.addStretch(1)
        b_add = QPushButton("＋ 添加模型"); b_add.setProperty("ghost", True)
        b_add.clicked.connect(self.add_row)
        b_ref = QPushButton("恢复官方参考价"); b_ref.setProperty("ghost", True)
        b_ref.clicked.connect(self.apply_reference)
        b_save = QPushButton("保存价格表"); b_save.clicked.connect(self.save_prices)
        for b in (b_add, b_ref, b_save):
            row.addWidget(b)
        root.addLayout(row)

        root.addWidget(QLabel("通用设置", objectName="SectionTitle"))
        gen = DH(); gen.setSpacing(10)
        gen.addWidget(QLabel("后端地址"))
        self.base_url = QLineEdit(self.store.get_kv("base_url")); gen.addWidget(self.base_url, 1)
        gen.addWidget(QLabel("端口"))
        self.port = QLineEdit(self.store.get_kv("port")); self.port.setFixedWidth(70)
        gen.addWidget(self.port)
        gen.addWidget(QLabel("档位虚拟模型（逗号分隔）"))
        self.base_models = QLineEdit(self.store.get_kv("effort_base_models"))
        gen.addWidget(self.base_models, 1)
        b_gen = QPushButton("保存并生效"); b_gen.setProperty("ghost", True)
        b_gen.clicked.connect(self.save_general)
        gen.addWidget(b_gen)
        root.addLayout(gen)

        login = DH(); login.setSpacing(10)
        self.login_state = QLabel(); self.login_state.setObjectName("PageSub")
        login.addWidget(self.login_state)
        login.addStretch(1)
        self.login_btn = QPushButton("重新登录（打开浏览器）")
        self.login_btn.clicked.connect(self.relogin)
        login.addWidget(self.login_btn)
        root.addLayout(login)
        root.addStretch(1)

        self.load_prices()

    # ---------- 价格表 ----------
    def load_prices(self):
        prices = self.store.get_prices()
        models = set(prices) | set(self.store.all_models_seen())
        live = set()
        if self.proxy:
            ms = self.proxy.list_models()
            if ms:
                live = {m.get("id") for m in ms.get("data", [])
                        if "-" not in m.get("id", "")
                        or m["id"].rsplit("-", 1)[1] not in EFFORT_LEVELS}
        self.price_table.setRowCount(0)
        for mid in sorted(models | live):
            self.append_price_row(mid, prices.get(mid))

    def append_price_row(self, model, p=None):
        row = self.price_table.rowCount()
        self.price_table.insertRow(row)
        live = model in live_set(self.proxy)
        self.price_table.setItem(row, 0, readonly_item(model))
        self.price_table.setCellWidget(row, 1, self._price_cell(p["input"] if p else None))
        self.price_table.setCellWidget(row, 2, self._price_cell(p["cached"] if p else None))
        self.price_table.setCellWidget(row, 3, self._price_cell(p["output"] if p else None))
        note = QLineEdit((p or {}).get("note") or "")
        self.price_table.setCellWidget(row, 4, note)
        btn = QPushButton("清空"); btn.setProperty("danger", True)
        btn.clicked.connect(lambda _, r=row: self.clear_row(r))
        self.price_table.setCellWidget(row, 5, btn)

    def _price_cell(self, value):
        w = QDoubleSpinBox()
        w.setRange(0, 100000)
        w.setDecimals(4)
        w.setSpecialValueText("未设置")
        w.setValue(value if value is not None else 0)
        w.setKeyboardTracking(False)
        return w

    def add_row(self):
        dlg = QDialog(self); dlg.setWindowTitle("添加自定义模型")
        v = DV(dlg)
        v.addWidget(QLabel("模型 id（与后端模型列表一致）"))
        name = QLineEdit(); v.addWidget(name)
        ok = QPushButton("添加"); ok.clicked.connect(dlg.accept)
        v.addWidget(ok)
        if dlg.exec() == QDialog.Accepted and name.text().strip():
            mid = name.text().strip()
            if not any(self.price_table.item(r, 0).text() == mid
                       for r in range(self.price_table.rowCount())):
                self.append_price_row(mid, None)

    def clear_row(self, row):
        for col in (1, 2, 3):
            self.price_table.cellWidget(row, col).setValue(0)

    def apply_reference(self):
        try:
            rate = float(self.rate.text() or "7.15")
        except ValueError:
            rate = 7.15
        for model, (i, ca, o, note) in REFERENCE_PRICES_USD.items():
            found = False
            for r in range(self.price_table.rowCount()):
                if self.price_table.item(r, 0).text() == model:
                    self.price_table.cellWidget(r, 1).setValue(round(i * rate, 4))
                    if ca is not None:
                        self.price_table.cellWidget(r, 2).setValue(round(ca * rate, 4))
                    self.price_table.cellWidget(r, 3).setValue(round(o * rate, 4))
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
            inp = self.price_table.cellWidget(r, 1).value() or None
            ca = self.price_table.cellWidget(r, 2).value() or None
            out = self.price_table.cellWidget(r, 3).value() or None
            note = self.price_table.cellWidget(r, 4).text().strip()
            if inp is None and ca is None and out is None:
                self.store.delete_price(model)
            else:
                self.store.set_price(model, inp, ca, out, note)
        self.store.set_kv("exchange_rate", self.rate.text().strip() or "7.15")
        QMessageBox.information(self, "已保存", "价格表已保存，立即对新请求生效。")

    # ---------- 通用 ----------
    def save_general(self):
        self.store.set_kv("base_url", self.base_url.text().strip())
        try:
            self.store.set_kv("port", str(int(self.port.text().strip())))
        except ValueError:
            pass
        self.store.set_kv("effort_base_models", self.base_models.text().strip())
        QMessageBox.information(
            self, "已保存",
            "设置已保存。后端地址/端口变更需重启程序生效。")

    def change_theme(self, name):
        self.store.set_kv("ui_theme", name)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.get(name))

    def relogin(self):
        self.login_btn.setEnabled(False)
        self.login_state.setText("正在打开浏览器等待登录…")
        def work():
            try:
                creds = auth.do_login(self.store.get_kv("base_url"))
                self.proxy.update_creds(creds)
                self.login_state.setText("登录成功，token 已验证有效。")
            except Exception as e:
                self.login_state.setText(f"登录失败：{e}")
            finally:
                from PySide6.QtCore import QMetaObject, Qt as QQt, Q_ARG
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


# ================================================================ 主窗口
class MainWindow(QMainWindow):
    def __init__(self, store, proxy, bridge):
        super().__init__()
        self.store, self.proxy, self.bridge = store, proxy, bridge
        self.setWindowTitle("chat2api 控制台")
        self.resize(1280, 820)

        central = QWidget(); self.setCentralWidget(central)
        layout = QHBoxLayout(central); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)

        # 侧边栏
        sidebar = QWidget(); sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(190)
        sv = QVBoxLayout(sidebar); sv.setContentsMargins(0, 12, 0, 0); sv.setSpacing(2)
        brand = QLabel("  chat2api 控制台")
        brand.setStyleSheet("font-size:14px;font-weight:700;color:#e8e8ed;padding:8px 14px 14px;")
        sv.addWidget(brand)
        self.nav = QListWidget()
        for label in ("◧  仪表盘", "▤  模型与思考档位", "⌘  API 密钥",
                      "☰  用量明细", "⚙  设置"):
            self.nav.addItem(label)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self.switch_page)
        sv.addWidget(self.nav, 1)
        self.status_box = QLabel(); self.status_box.setObjectName("StatusBox")
        self.status_box.setWordWrap(True)
        sv.addWidget(self.status_box)
        layout.addWidget(sidebar)

        # 页面
        self.stack = QStackedWidget()
        self.pages = [
            DashboardPage(store, proxy),
            ModelsPage(store, proxy),
            KeysPage(store, proxy),
            UsagePage(store, proxy),
            SettingsPage(store, proxy),
        ]
        for p in self.pages:
            self.stack.addWidget(p)
        layout.addWidget(self.stack, 1)

        self.bridge.stateChanged.connect(self.update_status)
        self.update_status({"state": proxy.state, "detail": proxy.state_detail})
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(
            lambda: self.update_status({"state": self.proxy.state,
                                        "detail": self.proxy.state_detail}))
        self.status_timer.start(3000)

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
            f"<div style='color:{color};font-weight:600'>{text}</div>"
            f"<div>监听 127.0.0.1:{port}</div>"
            + (f"<div style='color:#f2777a'>{detail}</div>" if detail else ""))
