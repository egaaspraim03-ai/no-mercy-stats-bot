#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import traceback
import threading
from bot import app

app = Flask(__name__)

BOT = None
BOT_ERROR = None

try:
    import bot as BOT
except Exception as e:
    BOT = None
    BOT_ERROR = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"


@app.route("/")
def health():
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


def _run_bg(mode: str):
    try:
        if hasattr(BOT, "run"):
            BOT.run(mode)
        elif hasattr(BOT, "main"):
            BOT.main(mode)
    except SystemExit:
        pass
    except Exception as e:
        try:
            if BOT and hasattr(BOT, "tg_send"):
                BOT.tg_send(
                    f"Извините пожалуйста, но я <b>обосрался</b> 💩\n"
                    f"<b>Где:</b> background\n"
                    f"<code>{type(e).__name__}: {e}</code>"
                )
        except Exception:
            pass


@app.route("/run")
def run_job():
    key = (request.args.get("key") or "").strip()
    mode = (request.args.get("mode") or os.environ.get("MODE") or "all").strip().lower()
    run_key = (os.environ.get("RUN_KEY") or "").strip()

    if not run_key:
        return jsonify({"ok": False, "error": "RUN_KEY not set"}), 500
    if key != run_key:
        return jsonify({"ok": False, "error": "bad key"}), 403
    if BOT is None:
        return jsonify({"ok": False, "error": "bot.py not loaded", "detail": BOT_ERROR}), 500

    # сразу ответ — работа в фоне
    t = threading.Thread(target=_run_bg, args=(mode,), daemon=True)
    t.start()

    return jsonify({
        "ok": True,
        "started": True,
        "mode": mode,
        "msg": "Работаю в фоне. Результат придёт в Telegram через 1–5 мин.",
    })


@app.route("/test-tg")
def test_tg():
    key = (request.args.get("key") or "").strip()
    run_key = (os.environ.get("RUN_KEY") or "").strip()
    if not run_key or key != run_key:
        return jsonify({"ok": False, "error": "bad key"}), 403
    if BOT is None:
        return jsonify({"ok": False, "error": "bot.py not loaded", "detail": BOT_ERROR}), 500
    try:
        BOT.tg_send("✅ Тест: бот жив, Telegram работает.")
        return jsonify({"ok": True, "msg": "sent test message"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
