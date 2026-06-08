#!/usr/bin/env python3
"""
画面共有シグナリングサーバー
使い方: python server.py
必要: pip install fastapi uvicorn websockets
"""

import asyncio
import json
import random
import string
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

app = FastAPI()

# セッション管理: { code: { "host": ws, "viewer": ws } }
sessions: dict = {}

def gen_code() -> str:
    while True:
        code = ''.join(random.choices(string.digits, k=6))
        if code not in sessions:
            return code

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    role = None
    code = None

    try:
        async for raw in ws.iter_text():
            msg = json.loads(raw)
            t = msg.get("type")

            # ホストが部屋を作成
            if t == "create":
                code = gen_code()
                sessions[code] = {"host": ws, "viewer": None}
                role = "host"
                await ws.send_text(json.dumps({"type": "created", "code": code}))

            # ビューワーが参加
            elif t == "join":
                code = msg.get("code")
                if code not in sessions or sessions[code]["host"] is None:
                    await ws.send_text(json.dumps({"type": "error", "msg": "コードが無効です"}))
                    continue
                if sessions[code]["viewer"] is not None:
                    await ws.send_text(json.dumps({"type": "error", "msg": "既に接続されています"}))
                    continue
                sessions[code]["viewer"] = ws
                role = "viewer"
                await ws.send_text(json.dumps({"type": "joined", "code": code}))
                # ホストに通知
                host_ws = sessions[code]["host"]
                await host_ws.send_text(json.dumps({"type": "viewer_joined"}))

            # offer/answer/candidate をそのまま転送
            elif t in ("offer", "answer", "candidate"):
                if code not in sessions:
                    continue
                s = sessions[code]
                # ホスト→ビューワー or ビューワー→ホスト
                target = s["viewer"] if role == "host" else s["host"]
                if target:
                    await target.send_text(raw)

    except WebSocketDisconnect:
        pass
    finally:
        if code and code in sessions:
            s = sessions[code]
            if role == "host":
                # ホストが切断したらセッション削除、ビューワーに通知
                if s["viewer"]:
                    try:
                        await s["viewer"].send_text(json.dumps({"type": "host_disconnected"}))
                    except:
                        pass
                del sessions[code]
            elif role == "viewer":
                s["viewer"] = None
                if s["host"]:
                    try:
                        await s["host"].send_text(json.dumps({"type": "viewer_disconnected"}))
                    except:
                        pass

# index.html を返す
@app.get("/")
async def index():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())

if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"

    print("=" * 50)
    print("  画面共有サーバー起動")
    print(f"  ローカル: http://localhost:8765")
    print(f"  LAN:      http://{local_ip}:8765")
    print("  終了: Ctrl+C")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="warning")
