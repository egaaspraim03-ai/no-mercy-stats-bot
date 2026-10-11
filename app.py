#!/usr/bin/env python3
import os
from flask import Flask, request, jsonify
import bot

app = Flask(__name__)


@app.get("/")
def health():
    return jsonify(
        {
            "ok": True,
            "service": "mangabuff-bot",
            "slug": bot.CLUB_SLUG,
            "proxy": bool(os.environ.get("PROXY")),
        }
    )


@app.get("/run")
@app.post("/run")
def run_job():
    key = request.args.get("key") or request.headers.get("X-Run-Key") or ""
    expect = os.environ.get("RUN_KEY", "").strip()
    if expect and key != expect:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    mode = (request.args.get("mode") or os.environ.get("MODE") or "all").strip()
    try:
        code = bot.run(mode)
        return jsonify({"ok": code == 0, "mode": mode, "code": code})
    except SystemExit as e:
        code = int(e.code) if isinstance(e.code, int) else 1
        return jsonify({"ok": False, "mode": mode, "code": code}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
