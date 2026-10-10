import os
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ.get("CHAT_ID", "-1004375644856")
MANGABUFF_SESSION = os.environ.get("MANGABUFF_SESSION", "")
XSRF_TOKEN = os.environ.get("XSRF_TOKEN", "")
FULL_COOKIE = os.environ.get("FULL_COOKIE", "")
CLUB_URL = os.environ.get("CLUB_URL", "https://mangabuff.ru/clubs/utinoe-bratstvo")
CLUB_NAME = os.environ.get("CLUB_NAME", "Утиное Братство")

MSK = timezone(timedelta(hours=3))

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=30)
    print("Telegram:", r.status_code)
    r.raise_for_status()

def get_club_data():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://mangabuff.ru/",
        "Origin": "https://mangabuff.ru",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    })

    if FULL_COOKIE:
        session.headers["Cookie"] = FULL_COOKIE
        print("✅ Используем FULL_COOKIE (все cookies)")
    else:
        if MANGABUFF_SESSION:
            session.cookies.set("mangabuff_session", MANGABUFF_SESSION, domain="mangabuff.ru", path="/")
        if XSRF_TOKEN:
            xsrf = unquote(XSRF_TOKEN).replace("%3D", "=")
            session.cookies.set("XSRF-TOKEN", xsrf, domain="mangabuff.ru", path="/")
            session.headers["X-XSRF-TOKEN"] = xsrf

    print("GET", CLUB_URL)
    r = session.get(CLUB_URL, timeout=45, allow_redirects=True)
    print("Status:", r.status_code)
    print("Final URL:", r.url)
    print("HTML length:", len(r.text))

    if r.status_code == 403:
        raise Exception("403 Forbidden — MangaBuff блокирует сервер (DDoS-Guard)")
    if "login" in r.url.lower() or "авторизац" in r.text.lower()[:2500]:
        raise Exception("Редирект на логин — cookie недействительна")

    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    result = {}
    rows = soup.select(".club-member, .members-list__item, .club__member, .member-item, [class*='member'], tr, .user-card, .club-users__item, li, .list-item")
    print("Rows:", len(rows))

    for row in rows:
        name_el = row.select_one("a[href*='/users/'], .nickname, .name, .username, a")
        if not name_el: continue
        name = name_el.get_text(strip=True)
        if not name or len(name) < 2: continue

        text = row.get_text(" ", strip=True)
        numbers = [int(x) for x in re.findall(r"\b(\d{1,5})\b", text)]
        day = week = None
        for n in numbers:
            if 0 <= n < 10000:
                if day is None: day = n
                elif week is None: week = n
                break
        if day is not None or week is not None:
            result[name] = {"day": day or 0, "week": week or 0}

    print("Members with numbers:", len(result))
    return result

def format_top(data, key, title):
    items = sorted([(n, v.get(key, 0)) for n, v in data.items()], key=lambda x: x[1], reverse=True)
    items = [x for x in items if x[1] > 0][:40]
    if not items:
        return f"❌ Нет данных: {title}\nКлуб: <b>{CLUB_NAME}</b>"

    lines = [f"<b>📊 {title}</b>", f"<i>{datetime.now(MSK).strftime('%d.%m.%Y %H:%M')} МСК</i>", f"Клуб: <b>{CLUB_NAME}</b>", ""]
    for i, (name, val) in enumerate(items, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} <b>{name}</b> — {val}")
    total = sum(v for _, v in items)
    lines += ["", f"<b>Всего:</b> {total}", f"В топе: {len(items)}"]
    return "\n".join(lines)

def main():
    mode = os.environ.get("MODE", "recent").lower()
    print("MODE =", mode)

    try:
        data = get_club_data()
    except Exception as e:
        send_telegram(f"❌ Ошибка:\n<code>{e}</code>")
        raise

    if mode == "daily":
        msg = format_top(data, "day", "Топ за день")
    elif mode == "weekly":
        msg = format_top(data, "week", "Топ за неделю")
    else:
        msg = format_top(data, "day", "Текущие вклады (день)")

    send_telegram(msg)
    print("OK")

if __name__ == "__main__":
    main()
