#!/usr/bin/env python3
"""
画面共有シグナリングサーバー
使い方: python server.py
必要: pip install aiohttp
"""

import asyncio
import json
import random
import string
import os
from aiohttp import web
import aiohttp

sessions = {}

def gen_code():
    while True:
        code = ''.join(random.choices(string.digits, k=6))
        if code not in sessions:
            return code

async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    role = None
    code = None

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            t = data.get("type")

            if t == "create":
                code = gen_code()
                sessions[code] = {"host": ws, "viewer": None}
                role = "host"
                await ws.send_json({"type": "created", "code": code})

            elif t == "join":
                code = data.get("code")
                if code not in sessions or sessions[code]["host"] is None:
                    await ws.send_json({"type": "error", "msg": "コードが無効です"})
                    continue
                if sessions[code]["viewer"] is not None:
                    await ws.send_json({"type": "error", "msg": "既に接続されています"})
                    continue
                sessions[code]["viewer"] = ws
                role = "viewer"
                await ws.send_json({"type": "joined", "code": code})
                await sessions[code]["host"].send_json({"type": "viewer_joined"})

            elif t in ("offer", "answer", "candidate"):
                if code not in sessions:
                    continue
                s = sessions[code]
                target = s["viewer"] if role == "host" else s["host"]
                if target:
                    await target.send_str(msg.data)

        elif msg.type == aiohttp.WSMsgType.ERROR:
            break

    # 切断処理
    if code and code in sessions:
        s = sessions[code]
        if role == "host":
            if s["viewer"]:
                try:
                    await s["viewer"].send_json({"type": "host_disconnected"})
                except:
                    pass
            del sessions[code]
        elif role == "viewer":
            s["viewer"] = None
            if s["host"]:
                try:
                    await s["host"].send_json({"type": "viewer_disconnected"})
                except:
                    pass

    return ws

async def index_handler(request):
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, encoding="utf-8") as f:
        return web.Response(text=f.read(), content_type="text/html")

import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

app = web.Application()
app.router.add_get("/", index_handler)
app.router.add_get("/ws", ws_handler)

if __name__ == "__main__":
    ip = get_local_ip()
    print("=" * 50)
    print("  画面共有サーバー起動")
    print(f"  ローカル: http://localhost:8765")
    print(f"  LAN:      http://{ip}:8765")
    print("  終了: Ctrl+C")
    print("=" * 50)
    web.run_app(app, host="0.0.0.0", port=8765, print=False)
