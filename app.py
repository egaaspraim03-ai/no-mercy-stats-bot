#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import traceback
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT = None
BOT_ERR = None
try:
    import bot as BOT
except Exception as e:
    BOT_ERR = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"


def _bg(mode: str):
    try:
        if BOT:
            BOT.run(mode)
    except SystemExit:
        pass
    except Exception as e:
        try:
            if BOT and hasattr(BOT, "tg_send"):
                BOT.tg_send(
                    f"Извините, обосрался 💩\nbackground\n<code>{type(e).__name__}: {e}</code>"
                )
        except Exception:
            pass


@app.route("/")
@app.route("/health")
def health():
    return jsonify({
        "ok": BOT is not None,
        "bot_loaded": BOT is not None,
        "error": BOT_ERR,
        "service": "no-mercy-stats-bot",
        "club": os.environ.get("CLUB_SLUG", ""),
        "token_set": bool(os.environ.get("BOT_TOKEN")),
        "chat_id_set": bool(os.environ.get("CHAT_ID")),
        "cookie_set": bool(os.environ.get("FULL_COOKIE")),
        "run_key_set": bool(os.environ.get("RUN_KEY")),
    })


@app.route("/test-tg")
def test_tg():
    key = (request.args.get("key") or "").strip()
    run_key = (os.environ.get("RUN_KEY") or "").strip()
    if not run_key or key != run_key:
        return jsonify({"ok": False, "error": "bad key"}), 403
    if BOT is None:
        return jsonify({"ok": False, "error": "bot.py not loaded", "detail": BOT_ERR}), 500
    try:
        BOT.tg_send("✅ Тест: бот жив, Telegram работает.")
        return jsonify({"ok": True, "msg": "sent test message"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/run")
def run_job():
    key = (request.args.get("key") or "").strip()
    mode = (request.args.get("mode") or "all").strip().lower()
    run_key = (os.environ.get("RUN_KEY") or "").strip()
    if not run_key or key != run_key:
        return jsonify({"ok": False, "error": "bad key"}), 403
    if BOT is None:
        return jsonify({"ok": False, "error": "bot.py not loaded", "detail": BOT_ERR}), 500
    t = threading.Thread(target=_bg, args=(mode,), daemon=True)
    t.start()
    return jsonify({
        "ok": True,
        "started": True,
        "mode": mode,
        "msg": "Работаю в фоне. Результат в Telegram через 1–5 мин.",
    })
