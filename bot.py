import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MANGABUFF_SESSION = os.environ.get("MANGABUFF_SESSION", "")
CLUB_URL = "https://mangabuff.ru/clubs/no-mercy"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    print("Telegram response:", r.status_code, r.text[:300])
    r.raise_for_status()

def get_stats():
    session = requests.Session()
    session.headers.update(HEADERS)
    if MANGABUFF_SESSION:
        session.cookies.set("mangabuff_session", MANGABUFF_SESSION, domain="mangabuff.ru")

    r = session.get(CLUB_URL, timeout=40)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    members = []

    # Пытаемся найти блоки участников (несколько вариантов селекторов)
    candidates = soup.select(
        ".club-member, .members-list__item, .club__member, .member-item, "
        "[class*='member'], tr, .user-card, .club-users__item"
    )

    for row in candidates:
        # Имя
        name_el = row.select_one("a[href*='/users/'], .nickname, .name, .username, a")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name or len(name) < 2:
            continue

        # Число вкладов (ищем цифры рядом)
        text = row.get_text(" ", strip=True)
        numbers = re.findall(r"\b(\d{1,5})\b", text)
        week = None
        for n in numbers:
            val = int(n)
            # разумный диапазон вкладов за неделю
            if 0 < val < 5000:
                week = val
                break

        if week is not None:
            members.append((name, week))

    # Убираем дубли
    unique = {}
    for name, week in members:
        unique[name] = max(unique.get(name, 0), week)

    return sorted(unique.items(), key=lambda x: x[1], reverse=True)

def format_message(members):
    if not members:
        return (
            "❌ Не удалось спарсить вклады.\n\n"
            "Возможные причины:\n"
            "• cookies устарели\n"
            "• сайт изменил вёрстку\n"
            "• нужна авторизация\n\n"
            "Открой Actions → логи и пришли ошибку."
        )

    lines = [
        f"<b>📊 Вклады за неделю — No Mercy</b>",
        f"<i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
        "",
    ]
    for i, (name, week) in enumerate(members[:40], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} <b>{name}</b> — {week}")

    total = sum(w for _, w in members)
    lines += ["", f"<b>Всего:</b> {total} вкладов", f"Участников: {len(members)}"]
    return "\n".join(lines)

def main():
    try:
        members = get_stats()
        print(f"Найдено: {len(members)}")
        msg = format_message(members)
        send_telegram(msg)
        print("OK")
    except Exception as e:
        send_telegram(f"❌ Ошибка бота:\n<code>{e}</code>")
        raise

if __name__ == "__main__":
    main()
