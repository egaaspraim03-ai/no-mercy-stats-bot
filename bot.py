import os
import re
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ.get("CHAT_ID", "-1004375644856")
MANGABUFF_SESSION = os.environ.get("MANGABUFF_SESSION", "")
CLUB_URL = "https://mangabuff.ru/clubs/utinoe-bratstvo"
CLUB_NAME = "Утиное Братство"

MSK = timezone(timedelta(hours=3))
STATE_FILE = Path("state.json")

HEADERS = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36", "Accept-Language": "ru-RU,ru;q=0.9"}

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=30)

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {"day": {}, "week": {}, "history": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def get_club_data():
    session = requests.Session()
    session.headers.update(HEADERS)
    if MANGABUFF_SESSION:
        session.cookies.set("mangabuff_session", MANGABUFF_SESSION, domain="mangabuff.ru")

    r = session.get(CLUB_URL, timeout=40)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    result = {}
    rows = soup.select(".club-member, .members-list__item, .club__member, .member-item, [class*='member'], tr, .user-card, .club-users__item")
    for row in rows:
        name_el = row.select_one("a[href*='/users/'], .nickname, .name, .username, a")
        if not name_el: continue
        name = name_el.get_text(strip=True)
        if not name or len(name) < 2: continue

        text = row.get_text(" ", strip=True).lower()
        numbers = [int(x) for x in re.findall(r"\b(\d{1,5})\b", text)]
        day = week = None
        for n in numbers:
            if 0 <= n < 10000:
                if day is None: day = n
                elif week is None: week = n
                break

        if day is not None or week is not None:
            result[name] = {"day": day or 0, "week": week or 0}
    return result

def format_top(data: dict, key: str, title: str):
    items = sorted([(n, v.get(key, 0)) for n, v in data.items()], key=lambda x: x[1], reverse=True)
    items = [x for x in items if x[1] > 0][:30]
    if not items: return f"❌ Нет данных: {title}"
    lines = [f"<b>📊 {title}</b>", f"<i>{datetime.now(MSK).strftime('%d.%m.%Y %H:%M')} МСК</i>", f"Клуб: <b>{CLUB_NAME}</b>", ""]
    for i, (name, val) in enumerate(items, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} <b>{name}</b> — {val}")
    total = sum(v for _, v in items)
    lines += ["", f"<b>Всего:</b> {total}", f"В топе: {len(items)}"]
    return "\n".join(lines)

def detect_new_contributors(old: dict, new: dict):
    changed = []
    for name, vals in new.items():
        old_val = old.get(name, {}).get("day", 0)
        new_val = vals.get("day", 0)
        if new_val > old_val:
            changed.append((name, new_val - old_val, new_val))
    changed.sort(key=lambda x: x[1], reverse=True)
    return changed

def format_recent(changed):
    if not changed: return f"ℹ️ Нет новых вкладов за день.\nКлуб: <b>{CLUB_NAME}</b>"
    lines = [f"<b>🆕 Последние, кто внёс</b>", f"<i>{datetime.now(MSK).strftime('%d.%m.%Y %H:%M')} МСК</i>", f"Клуб: <b>{CLUB_NAME}</b>", ""]
    for i, (name, delta, total) in enumerate(changed[:10], 1):
        lines.append(f"{i}. <b>{name}</b> +{delta} (сейчас {total})")
    return "\n".join(lines)

def main():
    mode = os.environ.get("MODE", "recent").lower()
    data = get_club_data()
    state = load_state()

    if mode == "daily":
        msg = format_top(data, "day", "Топ за день (за 10 мин до конца)")
        send_telegram(msg)
        state["day"] = data
    elif mode == "weekly":
        msg = format_top(data, "week", "Топ за неделю (за 10 мин до конца)")
        send_telegram(msg)
        state["week"] = data
    elif mode == "recent":
        old = state.get("day", {})
        changed = detect_new_contributors(old, data)
        state["day"] = data
        send_telegram(format_recent(changed))

    save_state(state)
    print("✅ Готово")

if __name__ == "__main__":
    main()
