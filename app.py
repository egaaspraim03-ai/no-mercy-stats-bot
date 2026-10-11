from flask import Flask, jsonify
import bot

app = Flask(__name__)

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "mangabuff-bot", "slug": bot.CLUB_SLUG, "proxy": bool(os.environ.get("PROXY"))})

@app.get("/run")
def run_job():
    key = request.args.get("key")
    expect = os.environ.get("RUN_KEY", "")
    if expect and key != expect:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    try:
        bot.run(request.args.get("mode"))
        return jsonify({"ok": True, "mode": request.args.get("mode")})
    except SystemExit as e:
        return jsonify({"ok": False, "code": int(e.code)}), 500
