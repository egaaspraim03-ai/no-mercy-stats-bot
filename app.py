#!/usr/bin/env python3
# app.py — новый чистый для Render (без ошибок)

from flask import Flask, request, jsonify
import sys
import traceback

try:
    from bot import run, now_msk, die, send_telegram, headers, proxies
    HAS_BOT = True
except ImportError:
    HAS_BOT = False
    print("ERROR: No bot.py or import failed", file=sys.stderr)

app = Flask(__name__)

@app.route("/")
def health():
    return jsonify({
        "ok": True,
        "service": "mangabuff-bot",
        "slug": "utinoe-bratstvo",
        "proxy": bool(os.environ.get("PROXY"))
    })

@app.route("/run", methods=["GET", "POST"])
def run_job():
    key = request.args.get("key") or request.headers.get("X-Run-Key", "")
    expect = os.environ.get("RUN_KEY", "").strip()
    if expect and key != expect:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    mode = request.args.get("mode", os.environ.get("MODE", "all")).strip().lower()
    try:
        if HAS_BOT and "bot" in globals():
            code = run(mode)
            return jsonify({"ok": code == 0, "mode": mode, "code": code})
        else:
            return jsonify({"ok": False, "error": "bot.py not loaded"}), 500
    except SystemExit as e:
        code = int(getattr(e, 'code', 1))
        return jsonify({"ok": False, "mode": mode, "code": code}), 500
    except Exception as e:
        print(f"UNHANDLED: {type(e).__name__}: {e}", file=sys.stderr)
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
