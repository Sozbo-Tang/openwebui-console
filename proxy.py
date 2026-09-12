#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""proxy.py — 本地 OpenAI 兼容代理（独立线程）：
转发到 Open WebUI、旁路采集 token 用量、本地 API key 鉴权、思考档位注入。"""
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

import auth
from core import (EFFORT_LEVELS, Store, calc_cost, now_str,
                         resolve_effort, slim_context)

CHUNK_EXCEPTIONS = (requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ConnectionError)


def validate_ok(store: Store, creds: dict):
    return auth.validate_creds(store.get_kv("base_url"), creds) is True


class ProxyServer:
    """持有凭证与状态，在后台线程跑 HTTP 服务。"""

    def __init__(self, store: Store, creds: dict, on_request=None, on_state=None):
        self.store = store
        self.creds = creds or {}      # {'token':…, 'api_key':…} 或 {}
        self.on_request = on_request  # 回调：每条请求记录（UI 实时刷新）
        self.on_state = on_state      # 回调：状态变化 {'state':…,'detail':…}
        self.state = "starting"
        self.state_detail = ""
        self.models_cache = {"at": 0, "data": None}
        self._httpd = None
        self._thread = None
        # 上游连接池：复用 TCP/TLS 连接，避免每次请求重新握手
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=8)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # ---------- 状态 ----------
    def set_state(self, state: str, detail: str = ""):
        self.state, self.state_detail = state, detail
        if self.on_state:
            try:
                self.on_state({"state": state, "detail": detail})
            except Exception:
                pass

    def bearer(self) -> str:
        return self.creds.get("api_key") or self.creds.get("token") or ""

    def update_creds(self, creds: dict):
        self.creds = creds or {}
        self.models_cache = {"at": 0, "data": None}
        if validate_ok(self.store, self.creds):
            self.set_state("ok", "")
        else:
            self.set_state("bad_creds", "凭证缺失或已失效，请在「设置」里重新登录")

    # ---------- 后端请求 ----------
    def backend(self, method: str, path: str, stream: bool = False, **kw):
        base = self.store.get_kv("base_url")
        timeout = kw.pop("timeout", 600)
        if isinstance(timeout, int):
            timeout = (10, timeout)
        return self.session.request(
            method, f"{base}{path}",
            headers={"Authorization": f"Bearer {self.bearer()}",
                     **kw.pop("headers", {})},
            timeout=timeout, stream=stream, **kw)

    def list_models(self, force=False):
        now = time.time()
        if self.models_cache["data"] is None or force \
                or now - self.models_cache["at"] > 60:
            r = self.backend("GET", "/api/models", timeout=20)
            if r.status_code == 200:
                self.models_cache = {"at": now, "data": r.json()}
        data = self.models_cache["data"]
        if data is None:
            return None
        data = dict(data)
        data["data"] = list(data.get("data", []))
        # 跟随客户端模式：追加思考档位虚拟模型
        if self.store.get_kv("effort_mode") == "follow_client":
            for base in self.store.effort_base_models():
                src = next((m for m in data["data"] if m.get("id") == base), None)
                for suffix in EFFORT_LEVELS:
                    vid = f"{base}-{suffix}"
                    if any(m.get("id") == vid for m in data["data"]):
                        continue
                    m = dict(src) if src else {}
                    m["id"] = vid
                    m["name"] = vid
                    data["data"].append(m)
        return data

    # ---------- 生命周期 ----------
    def start(self, port=None):
        host = self.store.get_kv("host")
        port = int(port or self.store.get_kv("port"))
        self._httpd = ThreadingHTTPServer((host, port), Handler)
        self._httpd.proxy = self
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        daemon=True, name="chat2api-proxy")
        self._thread.start()
        threading.Thread(target=self._warm_up, daemon=True,
                         name="chat2api-warmup").start()
        if validate_ok(self.store, self.creds):
            self.set_state("ok", "")
        elif self.creds:
            self.set_state("bad_creds", "凭证已失效，请在「设置」里重新登录")
        else:
            self.set_state("no_creds", "尚未登录，请在「设置」里重新登录")

    def _warm_up(self):
        """提前完成 DNS/TLS 握手，保持连接池热连接；首个聊天请求省去握手耗时。"""
        for _ in range(5):
            if self.creds:
                break
            time.sleep(0.3)
        try:
            self.session.get(f"{self.store.get_kv('base_url')}/api/version",
                             timeout=(10, 15))
        except Exception:
            pass

    def stop(self):
        if self._httpd:
            threading.Thread(target=self._httpd.shutdown, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    disable_nagle_algorithm = True   # SSE 小块立即发送，减少微延迟

    # ---------- 工具 ----------
    def _json(self, code: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if getattr(self, "close_connection", False):
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, message: str, detail=None):
        # 错误响应必须关闭连接：请求体可能未被读取（如未知路径 404），
        # 若 keep-alive 复用，残留的 body 字节会被下一条请求误当请求行，
        # 产生 "501 Unsupported method ({json}POST)" 这类错位错误。
        self.close_connection = True   # 先置标记，_json 据此发送 Connection: close
        self._json(code, {"error": {"message": message,
                                    "type": "chat2api_error", "detail": detail}})

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n == 0:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass  # 访问日志静默（UI 里有记账）

    # ---------- 本地 key 鉴权 ----------
    def _auth_key(self):
        """返回 (key_row|None, ok)。本地没有任何 key 时开放访问（记为“无 key”）。"""
        header = self.headers.get("Authorization") or ""
        bearer = header[7:].strip() if header.startswith("Bearer ") else ""
        store: Store = self.server.proxy.store
        with store.lock:
            keys = store.conn.execute(
                "SELECT * FROM api_keys WHERE revoked=0").fetchall()
        if not keys:
            return None, True
        for k in keys:
            if bearer and bearer == k["key"]:
                return k, True
        return None, False

    # ---------- GET ----------
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        px: ProxyServer = self.server.proxy

        if path in ("/", "/health"):
            self._json(200, {"status": "ok", "backend": px.store.get_kv("base_url"),
                             "state": px.state})
        elif path == "/v1/version":
            try:
                r = px.session.get(f"{px.store.get_kv('base_url')}/api/version",
                                   timeout=(10, 15))
                self._json(200, {"openwebui": r.json() if r.status_code == 200 else None,
                                 "chat2api_gui": "1.0.0"})
            except Exception as e:
                self._error(502, "后端不可达", str(e))
        elif path in ("/v1/models", "/api/models"):
            models = px.list_models(force=True)
            if models is None:
                self._error(502, "获取模型列表失败", "后端不可达或凭证失效")
                return
            self._json(200, models)
        else:
            self._error(404, f"未知路径: {path}")

    # ---------- POST ----------
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/v1/chat/completions", "/api/chat/completions"):
            self._chat()
        else:
            self._error(404, f"未知路径: {path}")

    # ---------- 聊天主流程 ----------
    def _chat(self):
        px: ProxyServer = self.server.proxy
        store: Store = px.store
        t0 = time.monotonic()

        key_row, ok = self._auth_key()
        if not ok:
            self._record(px, None, "", "", None, status=401,
                         error="无效的本地 API key")
            self._error(401, "Invalid API key",
                        "请在客户端填入本程序签发的 sk- 密钥")
            return

        body = self._read_body()
        if not body.get("messages"):
            self._error(400, "请求体缺少 messages 字段")
            return

        requested = body.get("model") or ""
        # 1) 虚拟模型 → 基础模型 + 档位（跟随客户端模式）
        base, effort = resolve_effort(requested, store.effort_base_models())
        # 2) 强制档位模式：用 UI 里给该模型设置的档位覆盖
        if store.get_kv("effort_mode") == "force":
            effort = store.get_level(base or requested)  # None = 后端默认
        real_model = base if base else requested

        fwd = slim_context(dict(body), store)
        fwd["model"] = real_model
        if effort:
            fwd["reasoning_effort"] = effort
        stream = bool(fwd.get("stream"))
        if stream and not fwd.get("stream_options"):
            fwd["stream_options"] = {"include_usage": True}

        try:
            r = px.backend("POST", "/api/chat/completions", stream=stream, json=fwd)
        except requests.RequestException as e:
            self._record(px, key_row, requested, real_model, effort, stream=stream,
                         status=0, error=f"连接后端失败: {type(e).__name__}")
            px.set_state("backend_down", f"后端连接失败: {type(e).__name__}")
            self._error(502, "后端不可达", str(e)[:200])
            return

        if r.status_code == 401:
            r.close()
            self._record(px, key_row, requested, real_model, effort, stream=stream,
                         status=401, error="上游 401：凭证失效，请在设置里重新登录")
            px.set_state("bad_creds", "凭证已失效，请在「设置」里重新登录")
            self._error(502, "凭证失效", "上游返回 401，请在程序「设置」页重新登录")
            return
        if r.status_code != 200:
            detail = r.text[:300]
            r.close()
            self._record(px, key_row, requested, real_model, effort, stream=stream,
                         status=r.status_code, error=f"上游 HTTP {r.status_code}: {detail}")
            self._error(502, "上游请求失败", f"HTTP {r.status_code}: {detail}")
            return

        if not stream:
            try:
                data = r.json()
            except Exception:
                r.close()
                self._record(px, key_row, requested, real_model, effort,
                             status=200, error="上游响应不是合法 JSON")
                self._error(502, "上游响应异常", "不是合法 JSON")
                return
            r.close()
            u = data.get("usage") or {}
            if "prompt_tokens_details" in u:
                px.store.set_kv("upstream_reports_cache", "1")
            self._record(px, key_row, requested, real_model, effort,
                         prompt=u.get("prompt_tokens") or 0,
                         cached=((u.get("prompt_tokens_details") or {})
                                 .get("cached_tokens") or 0),
                         completion=u.get("completion_tokens") or 0,
                         reasoning=((u.get("completion_tokens_details") or {})
                                    .get("reasoning_tokens") or 0),
                         status=200,
                         duration_ms=int((time.monotonic() - t0) * 1000))
            self._json(200, data)
            return

        # ---- 流式：SSE 透传 + 旁路解析 usage + 断流自动重试 ----
        # 要点（全部踩过坑）：
        #   1. 事件必须用空行 \n\n 分隔，否则严格解析客户端拿不到内容；
        #   2. [DONE] 后立即停止读取并关闭下游连接；
        #   3. 大上下文时上游网关约 50s 无输出就掐线（prefill 卡顿），
        #      所以对上游的 200 响应头做惰性转发：拿到第一个数据行才向
        #      客户端发响应头；尚未发出任何字节时断流 → 自动换连接重试
        #      上游（最多 3 次），全部失败才回 502 让客户端重试。
        usage = {}
        broken = None
        client_started = False
        done = False
        attempts = 0
        while True:
            attempts += 1
            broken = None
            done = False
            try:
                r = px.backend("POST", "/api/chat/completions",
                               stream=True, json=fwd)
            except requests.RequestException as e:
                if not client_started and attempts < 3:
                    time.sleep(0.3)
                    continue
                self._record(px, key_row, requested, real_model, effort,
                             stream=1, status=0,
                             error=f"连接后端失败: {type(e).__name__}")
                px.set_state("backend_down", f"后端连接失败: {type(e).__name__}")
                self._error(502, "后端不可达", str(e)[:200])
                return
            if r.status_code == 401:
                r.close()
                self._record(px, key_row, requested, real_model, effort,
                             stream=1, status=401,
                             error="上游 401：凭证失效，请在设置里重新登录")
                px.set_state("bad_creds", "凭证已失效，请在「设置」里重新登录")
                self._error(502, "凭证失效", "上游返回 401，请在程序「设置」页重新登录")
                return
            if r.status_code != 200:
                detail = r.text[:300]
                r.close()
                if not client_started and attempts < 3:
                    time.sleep(0.3)
                    continue
                self._record(px, key_row, requested, real_model, effort,
                             stream=1, status=r.status_code,
                             error=f"上游 HTTP {r.status_code}: {detail}")
                self._error(502, "上游请求失败", f"HTTP {r.status_code}: {detail}")
                return
            try:
                for raw in r.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    if not client_started:
                        # 第一个数据行到达才向客户端发响应头
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Connection", "close")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        client_started = True
                    self.wfile.write((raw + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                    if raw.startswith("data: "):
                        payload = raw[6:].strip()
                        if payload == "[DONE]":
                            done = True
                            break
                    try:
                        d = json.loads(payload)
                        if d.get("usage"):
                            usage = d["usage"]
                            if "prompt_tokens_details" in usage:
                                px.store.set_kv("upstream_reports_cache", "1")
                    except Exception:
                            pass
            except (BrokenPipeError, ConnectionResetError):
                broken = "客户端断开"
            except CHUNK_EXCEPTIONS as e:
                broken = f"上游断流: {type(e).__name__}"
            finally:
                r.close()
            if done or client_started or not broken:
                break
            if attempts >= 3:
                self._record(px, key_row, requested, real_model, effort,
                             stream=1, status=502, error=broken)
                self._error(502, "上游无响应",
                            f"{broken}；已重试 {attempts} 次（大上下文时上游约 50s "
                            "无输出会被网关掐断，建议减少上下文或降低思考档位）")
                return
            time.sleep(0.3)
        if not client_started:
            # 重试耗尽前的正常空流（极罕见）：给客户端一个合法的空 SSE 结束
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        self.close_connection = True

        u = usage or {}
        self._record(px, key_row, requested, real_model, effort,
                     prompt=u.get("prompt_tokens") or 0,
                     cached=((u.get("prompt_tokens_details") or {})
                             .get("cached_tokens") or 0),
                     completion=u.get("completion_tokens") or 0,
                     reasoning=((u.get("completion_tokens_details") or {})
                                .get("reasoning_tokens") or 0),
                     status=200,
                     duration_ms=int((time.monotonic() - t0) * 1000),
                     stream=1, error=broken)

    # ---------- 记账 ----------
    def _record(self, px: ProxyServer, key_row, model: str, real_model: str,
                effort, prompt=0, cached=0, completion=0, reasoning=0,
                status=0, duration_ms=0, stream=0, error=None):
        prices = px.store.get_prices()
        cost, known = calc_cost(prices, real_model, prompt, cached, completion)
        ts = now_str()
        rec = {
            "ts": ts,
            "key_id": key_row["id"] if key_row else None,
            "model": model, "real_model": real_model, "effort": effort,
            "prompt_tokens": prompt, "cached_tokens": cached,
            "completion_tokens": completion, "reasoning_tokens": reasoning,
            "cost": cost, "cost_known": 1 if known else 0,
            "status": status, "duration_ms": duration_ms,
            "stream": stream, "error": error,
        }
        px.store.log_request(**rec)
        rec["key_name"] = key_row["name"] if key_row else "（无 key）"
        if px.on_request:
            try:
                px.on_request(rec)
            except Exception:
                pass
