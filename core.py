#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.py — 数据层：SQLite 存储、价格表与计费逻辑。"""
import os
import secrets
import sqlite3
import threading
from datetime import datetime

import sys as _sys
if getattr(_sys, "frozen", False):   # PyInstaller 打包运行
    DATA_DIR = os.path.expanduser("~/Library/Application Support/chat2api-gui")
else:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "chat2api.db")
TOKEN_FILE = os.path.join(DATA_DIR, "token.json")

# 思考档位后缀 → reasoning_effort 值（国际通用 5 档，后端已实测全部支持）
EFFORT_LEVELS = {"Low": "low", "Medium": "medium", "High": "high",
                 "XHigh": "xhigh", "Max": "max"}

# 应用设置默认值
DEFAULTS = {
    "base_url": "https://chat.genai.um.edu.mo",
    "host": "127.0.0.1",
    "port": "8000",
    "exchange_rate": "7.15",                # 美元→人民币，仅供参考价预填换算
    "effort_mode": "follow_client",         # follow_client | force
    "effort_base_models": "GLM-5.3-Flash",  # 注册思考档位虚拟模型的基础模型（逗号分隔）
    "ui_theme": "",                         # 配色风格名（空=默认深色）
    "text_color": "white",                  # 字体颜色：black | white
    "language": "zh",                       # 界面语言：zh | en
    "bg_image": "",                         # 背景图片路径（JPEG）
    "ctx_tool_desc": "0",                   # 工具描述截断到 N 字符；0=不裁剪
    "ctx_max_history": "0",                 # 只保留最近 N 条非 system 消息；0=不裁剪
}


def slim_context(body: dict, store) -> dict:
    """按设置裁剪转发给上游的请求体（上下文瘦身，两项默认关闭）。
    - 工具描述截断：模型调用主要靠工具名与参数结构，长描述可压缩；
    - 历史裁剪：保留全部 system + 最近 N 条非 system 消息（会"失忆"，用户自行权衡）。"""
    try:
        tool_desc = int(store.get_kv("ctx_tool_desc") or 0)
        max_hist = int(store.get_kv("ctx_max_history") or 0)
    except ValueError:
        tool_desc = max_hist = 0
    if not tool_desc and not max_hist:
        return body
    out = dict(body)
    msgs = out.get("messages")
    if isinstance(msgs, list) and max_hist:
        sys_msgs = [m for m in msgs if m.get("role") == "system"]
        rest = [m for m in msgs if m.get("role") != "system"]
        if len(rest) > max_hist:
            out["messages"] = sys_msgs + rest[-max_hist:]
    tools = out.get("tools")
    if isinstance(tools, list) and tool_desc:
        slim = []
        for t in tools:
            if isinstance(t, dict) and isinstance(t.get("function"), dict):
                t = dict(t)
                fn = dict(t["function"])
                d = fn.get("description")
                if isinstance(d, str) and len(d) > tool_desc:
                    fn["description"] = d[:tool_desc] + "…"
                t["function"] = fn
            slim.append(t)
        out["tools"] = slim
    return out

# 官方参考价（USD / 1M tokens）——仅用于“恢复官方参考价”按钮预填。
# 来源：docs.z.ai、api-docs.deepseek.com（2026-09 查询）
REFERENCE_PRICES_USD = {
    "GLM-5.3-Flash":          (0.15, 0.03, 0.50, "z.ai 官方牌价"),
    "GLM-5.3":                (1.40, 0.26, 4.40, "z.ai 官方牌价"),
    "GLM-5.2":                (1.40, 0.26, 4.40, "z.ai 官方牌价"),
    "GLM-OCR":                (0.03, None, 0.03, "z.ai 官方牌价（无缓存价）"),
    "DeepSeek-V4-Flash-0731": (0.15, 0.003, 0.60, "官方非高峰价（高峰×2）"),
}


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def resolve_effort(requested: str, base_models: list):
    """虚拟模型 id（<base>-<Suffix>）→ (基础模型, effort|None)。
    不是虚拟模型时返回 (None, None)。"""
    for base in base_models:
        base = base.strip()
        if not base:
            continue
        if requested == base:
            return base, None
        prefix = base + "-"
        if requested.startswith(prefix):
            suffix = requested[len(prefix):]
            if suffix in EFFORT_LEVELS:
                return base, EFFORT_LEVELS[suffix]
    return None, None


class Store:
    """线程安全的 SQLite 存取（单连接 + 锁，个人使用规模足够）。"""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        for k, v in DEFAULTS.items():
            if self.get_kv(k) is None:
                self.set_kv(k, v)

    def _init_schema(self):
        with self.lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                key TEXT NOT NULL UNIQUE,
                created_at TEXT,
                revoked INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                key_id INTEGER,
                model TEXT,
                real_model TEXT,
                effort TEXT,
                prompt_tokens INTEGER DEFAULT 0,
                cached_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                reasoning_tokens INTEGER DEFAULT 0,
                cost REAL DEFAULT 0,
                cost_known INTEGER DEFAULT 0,
                status INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                stream INTEGER DEFAULT 0,
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_req_ts ON requests(ts);
            CREATE TABLE IF NOT EXISTS prices (
                model TEXT PRIMARY KEY,
                input_price REAL,
                cached_price REAL,
                output_price REAL,
                note TEXT
            );
            CREATE TABLE IF NOT EXISTS model_levels (
                model TEXT PRIMARY KEY,
                level TEXT
            );
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """)
            try:
                self.conn.execute("ALTER TABLE api_keys ADD COLUMN copyable INTEGER DEFAULT 1")
            except Exception:
                pass  # 列已存在
            self.conn.commit()

    # ---------------- 设置 (kv) ----------------
    def get_kv(self, key: str, default=None):
        with self.lock:
            row = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

    def set_kv(self, key: str, value):
        with self.lock:
            self.conn.execute(
                "INSERT INTO kv(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
            self.conn.commit()

    def effort_base_models(self) -> list:
        return [s.strip() for s in (self.get_kv("effort_base_models") or "").split(",")
                if s.strip()]

    # ---------------- API keys ----------------
    def create_key(self, name: str, copyable: bool = True) -> dict:
        key = "sk-" + secrets.token_urlsafe(24)
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO api_keys(name,key,created_at,copyable) VALUES(?,?,?,?)",
                (name, key, now_str(), 1 if copyable else 0))
            self.conn.commit()
            return {"id": cur.lastrowid, "name": name, "key": key}

    def find_key(self, bearer: str):
        """返回匹配的未吊销 key 行；找不到返回 None。"""
        if not bearer:
            return None
        with self.lock:
            return self.conn.execute(
                "SELECT * FROM api_keys WHERE key=? AND revoked=0",
                (bearer,)).fetchone()

    def revoke_key(self, key_id: int):
        with self.lock:
            self.conn.execute("UPDATE api_keys SET revoked=1 WHERE id=?", (key_id,))
            self.conn.commit()

    def key_count(self) -> int:
        with self.lock:
            return self.conn.execute(
                "SELECT COUNT(*) n FROM api_keys WHERE revoked=0").fetchone()["n"]

    def list_keys(self) -> list:
        """key 列表 + 今日/累计统计。"""
        today = today_str()
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM api_keys WHERE revoked=0 ORDER BY id").fetchall()
            out = []
            for r in rows:
                t = self.conn.execute("""
                    SELECT COUNT(*) n, COALESCE(SUM(prompt_tokens),0) pt,
                           COALESCE(SUM(completion_tokens),0) ct,
                           COALESCE(SUM(cached_tokens),0) ca,
                           COALESCE(SUM(cost),0) cost
                    FROM requests WHERE key_id=? AND substr(ts,1,10)=?""",
                    (r["id"], today)).fetchone()
                tot = self.conn.execute(
                    "SELECT COALESCE(SUM(cost),0) cost FROM requests WHERE key_id=?",
                    (r["id"],)).fetchone()
                out.append({"id": r["id"], "name": r["name"], "key": r["key"],
                            "created_at": r["created_at"], "copyable": r["copyable"],
                            "today_requests": t["n"], "today_prompt": t["pt"],
                            "today_completion": t["ct"], "today_cached": t["ca"],
                            "today_cost": t["cost"], "total_cost": tot["cost"]})
            return out

    # ---------------- 请求日志 ----------------
    def log_request(self, ts=None, key_id=None, model="", real_model="",
                    effort=None, prompt_tokens=0, cached_tokens=0,
                    completion_tokens=0, reasoning_tokens=0,
                    cost=0.0, cost_known=0, status=0, duration_ms=0,
                    stream=0, error=None):
        with self.lock:
            self.conn.execute("""INSERT INTO requests
                (ts,key_id,model,real_model,effort,prompt_tokens,cached_tokens,
                 completion_tokens,reasoning_tokens,cost,cost_known,status,
                 duration_ms,stream,error)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ts or now_str(), key_id, model, real_model, effort,
                 prompt_tokens, cached_tokens, completion_tokens,
                 reasoning_tokens, cost, cost_known, status, duration_ms,
                 stream, error))
            self.conn.commit()

    def recent_requests(self, limit: int = 50) -> list:
        with self.lock:
            rows = self.conn.execute("""
                SELECT r.*, COALESCE(k.name,'（无 key）') key_name
                FROM requests r LEFT JOIN api_keys k ON k.id=r.key_id
                ORDER BY r.id DESC LIMIT ?""", (limit,)).fetchall()
            return [dict(x) for x in rows]

    def query_requests(self, date_from=None, date_to=None, key_id=None,
                       model=None, limit: int = 1000) -> list:
        sql = """SELECT r.*, COALESCE(k.name,'（无 key）') key_name
                 FROM requests r LEFT JOIN api_keys k ON k.id=r.key_id WHERE 1=1"""
        args = []
        if date_from:
            sql += " AND substr(r.ts,1,10)>=?"
            args.append(date_from)
        if date_to:
            sql += " AND substr(r.ts,1,10)<=?"
            args.append(date_to)
        if key_id:
            sql += " AND r.key_id=?"
            args.append(key_id)
        if model:
            sql += " AND r.real_model=?"
            args.append(model)
        sql += " ORDER BY r.id DESC LIMIT ?"
        args.append(limit)
        with self.lock:
            return [dict(x) for x in self.conn.execute(sql, args).fetchall()]

    def today_stats(self) -> dict:
        today = today_str()
        with self.lock:
            r = self.conn.execute("""
                SELECT COUNT(*) n,
                       COALESCE(SUM(cost),0) cost,
                       COALESCE(SUM(prompt_tokens),0) pt,
                       COALESCE(SUM(completion_tokens),0) ct,
                       COALESCE(SUM(cached_tokens),0) ca,
                       COALESCE(SUM(CASE WHEN status!=200 THEN 1 ELSE 0 END),0) fail
                FROM requests WHERE substr(ts,1,10)=?""", (today,)).fetchone()
            y = self.conn.execute("""
                SELECT COALESCE(SUM(cost),0) cost FROM requests
                WHERE substr(ts,1,10)=date('now','-1 day','localtime')""").fetchone()
            t = self.conn.execute("""
                SELECT COALESCE(SUM(cost),0) cost, COUNT(*) n FROM requests""").fetchone()
            return {"requests": r["n"], "cost": r["cost"], "prompt": r["pt"],
                    "completion": r["ct"], "cached": r["ca"], "fail": r["fail"],
                    "yesterday_cost": y["cost"],
                    "total_cost": t["cost"], "total_requests": t["n"]}

    def model_stats_today(self) -> list:
        today = today_str()
        with self.lock:
            rows = self.conn.execute("""
                SELECT real_model m, COUNT(*) n,
                       SUM(prompt_tokens) pt, SUM(completion_tokens) ct,
                       SUM(cached_tokens) ca, SUM(cost) cost
                FROM requests WHERE substr(ts,1,10)=? AND real_model!=''
                GROUP BY real_model ORDER BY cost DESC""", (today,)).fetchall()
            return [dict(x) for x in rows]

    def all_models_seen(self) -> list:
        """出现过的所有模型（含已下线）——价格表合并展示用。"""
        with self.lock:
            rows = self.conn.execute(
                "SELECT DISTINCT real_model FROM requests WHERE real_model!=''").fetchall()
            return [r["real_model"] for r in rows]

    def usage_by_key_model(self, key_id=None, model=None, date_from=None):
        """按 (API key, 模型) 聚合的用量与费用（明细页数据源）。"""
        sql = """
            SELECT COALESCE(k.name,'（无 key）') key_name,
                   r.real_model model,
                   COUNT(*) requests,
                   COALESCE(SUM(r.prompt_tokens),0) prompt,
                   COALESCE(SUM(r.cached_tokens),0) cached,
                   COALESCE(SUM(r.completion_tokens),0) completion,
                   COALESCE(SUM(r.reasoning_tokens),0) reasoning,
                   COALESCE(SUM(r.cost),0) cost,
                   CASE WHEN SUM(r.cost_known)>0 THEN 1 ELSE 0 END cost_known,
                   SUM(CASE WHEN r.status!=200 THEN 1 ELSE 0 END) fails
            FROM requests r LEFT JOIN api_keys k ON k.id=r.key_id
            WHERE r.real_model!=''"""
        args = []
        if key_id:
            sql += " AND r.key_id=?"; args.append(key_id)
        if model:
            sql += " AND r.real_model=?"; args.append(model)
        if date_from:
            sql += " AND substr(r.ts,1,10)>=?"; args.append(date_from)
        sql += " GROUP BY r.key_id, r.real_model ORDER BY cost DESC"
        with self.lock:
            return [dict(x) for x in self.conn.execute(sql, args).fetchall()]

    # ---------------- 价格表 ----------------
    def get_prices(self) -> dict:
        """model -> {'input':…,'cached':…,'output':…,'note':…}"""
        with self.lock:
            rows = self.conn.execute("SELECT * FROM prices").fetchall()
            return {r["model"]: {"input": r["input_price"], "cached": r["cached_price"],
                                 "output": r["output_price"], "note": r["note"]}
                    for r in rows}

    def set_price(self, model: str, input_price, cached_price, output_price, note=""):
        with self.lock:
            self.conn.execute("""
                INSERT INTO prices(model,input_price,cached_price,output_price,note)
                VALUES(?,?,?,?,?)
                ON CONFLICT(model) DO UPDATE SET input_price=excluded.input_price,
                  cached_price=excluded.cached_price,
                  output_price=excluded.output_price, note=excluded.note""",
                (model, input_price, cached_price, output_price, note))
            self.conn.commit()

    def delete_price(self, model: str):
        with self.lock:
            self.conn.execute("DELETE FROM prices WHERE model=?", (model,))
            self.conn.commit()

    # ---------------- 每模型思考档位 ----------------
    def get_level(self, model: str):
        with self.lock:
            row = self.conn.execute(
                "SELECT level FROM model_levels WHERE model=?", (model,)).fetchone()
            return row["level"] if row else None

    def set_level(self, model: str, level):
        """level: none/low/medium/high，None=删除（跟随后端默认）"""
        with self.lock:
            if level:
                self.conn.execute("""
                    INSERT INTO model_levels(model,level) VALUES(?,?)
                    ON CONFLICT(model) DO UPDATE SET level=excluded.level""",
                    (model, level))
            else:
                self.conn.execute("DELETE FROM model_levels WHERE model=?", (model,))
            self.conn.commit()

    def all_levels(self) -> dict:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM model_levels").fetchall()
            return {r["model"]: r["level"] for r in rows}


def calc_cost(prices: dict, real_model: str, prompt_tokens: int,
              cached_tokens: int, completion_tokens: int):
    """按价格表计算费用（人民币）。
    返回 (cost, cost_known)。价格未设置的模型返回 (0, False)。
    计费：输入×(未命中×输入价 + 命中×缓存价) + 输出×输出价；
    缓存价未设置时按输入价计；reasoning tokens 已含在 completion_tokens 里。"""
    p = prices.get(real_model)
    if not p or p.get("input") is None:
        return 0.0, False
    cached = min(max(cached_tokens, 0), max(prompt_tokens, 0))
    uncached = max(prompt_tokens - cached, 0)
    cached_price = p.get("cached")
    if cached_price is None:
        cached_price = p["input"]
    cost = (uncached / 1e6 * p["input"]
            + cached / 1e6 * cached_price
            + completion_tokens / 1e6 * (p.get("output") or 0.0))
    return cost, True
