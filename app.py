from flask import Flask, request
import bot as BOT  # твой bot.py

app = Flask(__name__)

@app.route("/health")
def health():
    return {"ok": True, "bot_loaded": True, "service": "no-mercy-stats-bot"}

@app.route("/webhook", methods=["POST"])
def webhook():
    # логика обработки Telegram (если нужно)
    return "", 200

# Запуск
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
