#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""auth.py — Open WebUI 登录态管理：浏览器登录（Playwright）、token 验证、持久化。"""
import json
import os
import time
from pathlib import Path

import requests

from core import DATA_DIR
TOKEN_FILE = os.path.join(DATA_DIR, "token.json")
PROFILE_DIR = os.path.join(DATA_DIR, ".chrome-profile")
LEGACY_TOKEN_FILE = "/Users/tianhuatang/AI-Workflows/zcode/workspaces/chat2api-um-genai/token.json"

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


def find_chrome():
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None


class TokenStore:
    def __init__(self, path: str = TOKEN_FILE, url: str = ""):
        self.path = path
        self.url = url

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if self.url and data.get("url") != self.url:
                return None
            return data
        except Exception:
            return None

    def save(self, token: str, api_key: str = None):
        data = {"url": self.url, "token": token, "api_key": api_key,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.chmod(self.path, 0o600)
        return data


def validate_creds(base_url: str, creds: dict, timeout: int = 12):
    """验证凭证是否有效。返回 True/False；网络异常返回 None（未知）。"""
    bearer = creds.get("api_key") or creds.get("token") if creds else None
    if not bearer:
        return False
    try:
        r = requests.get(f"{base_url}/api/models",
                         headers={"Authorization": f"Bearer {bearer}"},
                         timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return None  # 网络问题，无法判定


def browser_login(base_url: str, profile_dir: str = PROFILE_DIR,
                  timeout_s: int = 240, log=print) -> str:
    """打开可见 Chrome 窗口等待登录，从 localStorage 读取 token。
    拿到 token 后先验证 /api/models，失效的旧 token 清掉重等真正登录。"""
    from playwright.sync_api import sync_playwright

    chrome = find_chrome()
    log("=" * 56)
    log(f"正在打开 Chrome 窗口: {base_url}")
    log("请在弹出的窗口中完成登录（SSO 有效时会自动跳过）。")
    log(f"等待登录完成，最长 {timeout_s} 秒...")
    log("=" * 56)

    with sync_playwright() as p:
        if chrome:
            ctx = p.chromium.launch_persistent_context(
                profile_dir, headless=False, executable_path=chrome)
        else:
            log("未找到系统 Chrome，使用 Playwright 自带 Chromium")
            ctx = p.chromium.launch_persistent_context(profile_dir, headless=False)

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log(f"[warn] 打开页面异常（可能仍在跳转登录）：{e}")

        deadline = time.time() + timeout_s
        warned = False
        while time.time() < deadline:
            try:
                token = page.evaluate("localStorage.getItem('token')")
                if token:
                    status = page.evaluate(
                        """async t => {
                            const r = await fetch('/api/models',
                                {headers: {Authorization: 'Bearer ' + t}});
                            return r.status;
                        }""", token)
                    if status == 200:
                        log("\n登录成功，token 已验证有效。")
                        ctx.close()
                        return token
                    if not warned:
                        warned = True
                        log("\n[warn] localStorage 里的旧 token 已失效，"
                            "清除并等待真正的重新登录...")
                    page.evaluate("localStorage.removeItem('token')")
            except Exception:
                pass
            page.wait_for_timeout(1000)

        ctx.close()
        raise RuntimeError(f"等待登录超时（{timeout_s}s）")


def fetch_api_key(base_url: str, token: str):
    """尽力获取 Open WebUI API Key（长期有效）。失败返回 None。"""
    for method in ("GET", "POST"):
        try:
            r = requests.request(
                method, f"{base_url}/api/v1/auths/api_key",
                headers={"Authorization": f"Bearer {token}"}, timeout=15)
            if r.status_code == 200:
                key = r.json().get("api_key")
                if key:
                    return key
        except Exception:
            pass
    return None


def load_creds(base_url: str, log=print) -> dict:
    """启动时加载凭证：本目录 token.json → 旧目录导入 → 无凭证。
    只验证有效性并返回；不做浏览器登录（由 UI 触发）。"""
    store = TokenStore(TOKEN_FILE, base_url)
    saved = store.load()
    if saved and (saved.get("api_key") or saved.get("token")):
        state = validate_creds(base_url, saved)
        if state:
            return {"token": saved.get("token"), "api_key": saved.get("api_key")}
        if state is False:
            log("[auth] 本目录已保存的凭证已失效")
    # 尝试从旧目录导入（url 匹配才有效）
    try:
        with open(LEGACY_TOKEN_FILE, "r", encoding="utf-8") as f:
            legacy = json.load(f)
        if legacy.get("url") == base_url and (legacy.get("token") or legacy.get("api_key")):
            state = validate_creds(base_url, legacy)
            if state:
                log("[auth] 已从 chat2api-um-genai 导入有效凭证")
                store.save(legacy.get("token"), legacy.get("api_key"))
                return {"token": legacy.get("token"), "api_key": legacy.get("api_key")}
            if state is False:
                log("[auth] 旧目录凭证也已失效")
    except Exception:
        pass
    return {}


def do_login(base_url: str, use_api_key: bool = False, log=print) -> dict:
    """执行一次真实登录并保存。供 UI 的“重新登录”按钮调用。"""
    token = browser_login(base_url, log=log)
    api_key = fetch_api_key(base_url, token) if use_api_key else None
    TokenStore(TOKEN_FILE, base_url).save(token, api_key)
    return {"token": token, "api_key": api_key}
