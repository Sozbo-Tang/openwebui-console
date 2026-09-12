#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""main.py — chat2api GUI 启动入口。
用法：python3 main.py [--port 8000] [--base-url https://…]"""
import os
import sys

os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

import auth
import lang
import theme
from core import Store
from proxy import ProxyServer
from ui import MainWindow


class Bridge(QObject):
    """代理线程 → UI 线程的信号桥（Qt 信号跨线程发射是安全的）。"""
    requestLogged = Signal(dict)
    stateChanged = Signal(dict)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="chat2api GUI")
    ap.add_argument("--port", type=int, help="覆盖监听端口")
    ap.add_argument("--base-url", help="覆盖 Open WebUI 地址")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("chat2api 控制台")

    store = Store()
    lang.LANG = store.get_kv("language") or "zh"
    if args.port:
        store.set_kv("port", str(args.port))
    if args.base_url:
        store.set_kv("base_url", args.base_url)

    bridge = Bridge()
    creds = auth.load_creds(store.get_kv("base_url"))
    proxy = ProxyServer(
        store, creds,
        on_request=bridge.requestLogged.emit,
        on_state=bridge.stateChanged.emit)
    proxy.start()

    win = MainWindow(store, proxy, bridge)
    win.show()
    app.aboutToQuit.connect(proxy.stop)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
