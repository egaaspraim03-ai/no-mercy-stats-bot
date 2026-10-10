import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ.get("CHAT_ID", "-1004375644856")
MANGABUFF_SESSION = os.environ.get("MANGABUFF_SESSION", "")
CLUB_URL = "https://mangabuff.ru/clubs/kafe-anteiku"
CLUB_NAME = "Кафе Антейку"

# Файл для хранения прошлых данных (для "кто только что внёс")
STATE_FILE = Path("state.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

MSK = timezone(timedelta(hours=3))

def send_telegram(text: str, chat_id=None):
    chat_id = chat_id or CHAT_ID
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=30)
    print("TG:", r.status_code)
    return r.ok

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"day": {}, "week": {}, "history": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def get_club_data():
    """Парсит день и неделю. Возвращает dict name -> {day, week}"""
    session = requests.Session()
    session.headers.update(HEADERS)
    if MANGABUFF_SESSION:
        session.cookies.set("mangabuff_session", MANGABUFF_SESSION, domain="mangabuff.ru")

    r = session.get(CLUB_URL, timeout=40)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    result = {}

    # Универсальный поиск блоков участников
    rows = soup.select(
        ".club-member, .members-list__item, .club__member, .member-item, "
        "[class*='member'], tr, .user-card, .club-users__item, .list-item, li"
    )

    for row in rows:
        name_el = row.select_one("a[href*='/users/'], .nickname, .name, .username, a")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name or len(name) < 2 or name.lower() in ("участники", "members"):
            continue

        text = row.get_text(" ", strip=True).lower()
        numbers = [int(x) for x in re.findall(r"\b(\d{1,5})\b", text)]

        day = week = None
        # Часто на странице: день / неделя / всего — берём первые разумные
        for n in numbers:
            if 0 <= n < 10000:
                if day is None:
                    day = n
                elif week is None:
                    week = n
                    break

        if day is not None or week is not None:
            result[name] = {
                "day": day if day is not None else 0,
                "week": week if week is not None else 0,
            }

    return result

def format_top(data: dict, key: str, title: str, limit=30):
    items = sorted(
        [(n, v.get(key, 0)) for n, v in data.items()],
        key=lambda x: x[1], reverse=True
    )
    items = [x for x in items if x[1] > 0][:limit]

    if not items:
        return f"❌ Нет данных: {title}\n(возможно нужна cookie или сайт изменился)"

    lines = [
        f"<b>📊 {title}</b>",
        f"<i>{datetime.now(MSK).strftime('%d.%m.%Y %H:%M')} МСК</i>",
        f"Клуб: <b>{CLUB_NAME}</b>",
        "",
    ]
    for i, (name, val) in enumerate(items, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} <b>{name}</b> — {val}")

    total = sum(v for _, v in items)
    lines += ["", f"<b>Всего:</b> {total}", f"В топе: {len(items)}"]
    return "\n".join(lines)

def detect_new_contributors(old: dict, new: dict, key="day"):
    """Кто прибавил вклады с прошлого раза"""
    changed = []
    for name, vals in new.items():
        old_val = old.get(name, {}).get(key, 0)
        new_val = vals.get(key, 0)
        if new_val > old_val:
            changed.append((name, new_val - old_val, new_val))
    changed.sort(key=lambda x: x[1], reverse=True)
    return changed

def format_recent(changed, limit=10):
    if not changed:
        return (
            f"ℹ️ За последнее время новых вкладов не видно.\n"
            f"Клуб: <b>{CLUB_NAME}</b>\n"
            f"Попробуй через несколько минут или добавь cookie."
        )
    lines = [
        f"<b>🆕 Последние, кто внёс карты</b>",
        f"<i>{datetime.now(MSK).strftime('%d.%m.%Y %H:%M')} МСК</i>",
        f"Клуб: <b>{CLUB_NAME}</b>",
        "",
    ]
    for i, (name, delta, total) in enumerate(changed[:limit], 1):
        lines.append(f"{i}. <b>{name}</b> +{delta} (сейчас {total})")
    return "\n".join(lines)

# ===== РЕЖИМЫ ДЛЯ GITHUB ACTIONS =====
def mode_daily():
    data = get_club_data()
    state = load_state()
    msg = format_top(data, "day", "Топ за день (за 10 мин до конца)")
    send_telegram(msg)
    state["day"] = data
    save_state(state)

def mode_weekly():
    data = get_club_data()
    state = load_state()
    msg = format_top(data, "week", "Топ за неделю (за 10 мин до конца)")
    send_telegram(msg)
    state["week"] = data
    save_state(state)

def mode_recent():
    data = get_club_data()
    state = load_state()
    old = state.get("day", {})
    changed = detect_new_contributors(old, data, "day")
    # обновляем историю
    hist = state.get("history", [])
    for name, delta, total in changed:
        hist.insert(0, {"name": name, "delta": delta, "total": total, "ts": datetime.now(MSK).isoformat()})
    state["history"] = hist[:50]
    state["day"] = data
    save_state(state)
    send_telegram(format_recent(changed, 10))

# ===== LIVE-БОТ С КОМАНДАМИ =====
def run_polling_bot():
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Бот статистики клуба «Кафе Антейку»\n\n"
            "/topday — топ за день\n"
            "/topweek — топ за неделю\n"
            "/recent — последние 10, кто внёс\n"
            "/now — то же, что /recent"
        )

    async def topday(update: Update, context: ContextTypes.DEFAULT_TYPE):
        data = get_club_data()
        await update.message.reply_html(format_top(data, "day", "Топ за день"))

    async def topweek(update: Update, context: ContextTypes.DEFAULT_TYPE):
        data = get_club_data()
        await update.message.reply_html(format_top(data, "week", "Топ за неделю"))

    async def recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
        data = get_club_data()
        state = load_state()
        old = state.get("day", {})
        changed = detect_new_contributors(old, data, "day")
        state["day"] = data
        save_state(state)
        await update.message.reply_html(format_recent(changed, 10))

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("topday", topday))
    app.add_handler(CommandHandler("topweek", topweek))
    app.add_handler(CommandHandler("recent", recent))
    app.add_handler(CommandHandler("now", recent))
    print("Bot polling started...")
    app.run_polling()

if __name__ == "__main__":
    mode = os.environ.get("MODE", "recent").lower()
    if mode == "daily":
        mode_daily()
    elif mode == "weekly":
        mode_weekly()
    elif mode == "recent":
        mode_recent()
    elif mode == "polling":
        run_polling_bot()
    else:
        mode_recent()
