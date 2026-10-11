#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask entrypoint for Render (no-mercy-stats-bot)
Start Command:
  gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300 --workers 1
"""

import os
import traceback
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---- безопасный импорт bot.py ----
BOT = None
BOT_ERROR = None

try:
    import bot as BOT
except Exception as e:
    BOT = None
    BOT_ERROR = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"


@app.route("/")
def health():
    """Проверка: жив ли сервис и загружен ли bot.py"""
    return jsonify({
        "ok": BOT is not None,
        "bot_loaded": BOT is not None,
        "error": BOT_ERROR,
        "service": "no-mercy-stats-bot",
        "club": os.environ.get("CLUB_SLUG", ""),
        "chat_id_set": bool(os.environ.get("CHAT_ID")),
        "cookie_set": bool(os.environ.get("FULL_COOKIE")),
        "token_set": bool(os.environ.get("BOT_TOKEN")),
        "proxy_set": bool(os.environ.get("PROXY")),
        "run_key_set": bool(os.environ.get("RUN_KEY")),
    })


@app.route("/run")
def run_job():
    """
    Триггер:
      /run?key=ТВОЙ_RUN_KEY&mode=all
      mode: all | day | week | month | past_month | today | recent | history
    """
    key = (request.args.get("key") or "").strip()
    mode = (request.args.get("mode") or os.environ.get("MODE") or "all").strip().lower()
    run_key = (os.environ.get("RUN_KEY") or "").strip()

    if not run_key:
        return jsonify({"ok": False, "error": "RUN_KEY not set in Environment"}), 500

    if key != run_key:
        return jsonify({"ok": False, "error": "bad key"}), 403

    if BOT is None:
        return jsonify({
            "ok": False,
            "error": "bot.py not loaded",
            "detail": BOT_ERROR,
        }), 500

    try:
        if hasattr(BOT, "run"):
            result = BOT.run(mode)
        elif hasattr(BOT, "main"):
            result = BOT.main(mode)
        else:
            return jsonify({"ok": False, "error": "bot.py has no run() or main()"}), 500

        return jsonify({"ok": True, "mode": mode, "result": str(result)})
    except SystemExit as e:
        # die() внутри bot.py
        return jsonify({
            "ok": False,
            "error": "SystemExit (die)",
            "detail": str(e),
        }), 500
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": type(e).__name__,
            "detail": str(e),
            "trace": traceback.format_exc()[-2000:],
        }), 500


@app.route("/test-tg")
def test_tg():
    """Быстрая проверка Telegram без MangaBuff"""
    key = (request.args.get("key") or "").strip()
    run_key = (os.environ.get("RUN_KEY") or "").strip()
    if not run_key or key != run_key:
        return jsonify({"ok": False, "error": "bad key"}), 403

    if BOT is None:
        return jsonify({"ok": False, "error": "bot.py not loaded", "detail": BOT_ERROR}), 500

    try:
        if hasattr(BOT, "tg_send"):
            BOT.tg_send("✅ Тест: бот жив, Telegram работает.")
            return jsonify({"ok": True, "msg": "sent test message"})
        return jsonify({"ok": False, "error": "tg_send not found in bot"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
