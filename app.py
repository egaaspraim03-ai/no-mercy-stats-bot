#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import threading
from flask import Flask, request, jsonify

import bot as BOT

app = Flask(__name__)
RUN_KEY = os.environ.get("RUN_KEY", "duck2026").strip()


def _bg(mode: str):
    try:
        BOT.run(mode)
    except SystemExit:
        pass
    except Exception as e:
        print("bg crash:", e, flush=True)


@app.route("/")
@app.route("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "bot_loaded": True,
            "service": "no-mercy-stats-bot",
            "club": BOT.CLUB_SLUG,
            "token_set": bool(BOT.BOT_TOKEN),
            "chat_id_set": bool(BOT.CHAT_ID),
            "cookie_set": bool(BOT.FULL_COOKIE) and len(BOT.FULL_COOKIE) > 50,
            "cookie_len": len(BOT.FULL_COOKIE or ""),
            "run_key_set": bool(RUN_KEY),
            "proxy_set": bool(BOT.PROXY),
            "error": None,
        }
    )


@app.route("/test-tg")
def test_tg():
    key = (request.args.get("key") or "").strip()
    if key != RUN_KEY:
        return jsonify({"ok": False, "error": "bad key"}), 403
    BOT.tg_send("✅ Тест: бот жив, Telegram работает.")
    return jsonify({"ok": True, "msg": "sent test message"})


@app.route("/run")
def run_job():
    key = (request.args.get("key") or "").strip()
    mode = (request.args.get("mode") or "all").strip().lower()
    if key != RUN_KEY:
        return jsonify({"ok": False, "error": "bad key"}), 403
    t = threading.Thread(target=_bg, args=(mode,), daemon=True)
    t.start()
    return jsonify(
        {
            "ok": True,
            "started": True,
            "mode": mode,
            "msg": "Работаю в фоне. Результат в Telegram через 1–5 мин.",
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
