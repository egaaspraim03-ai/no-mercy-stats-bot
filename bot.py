#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MangaBuff club stats → Telegram
Render free, phone-friendly, без curl_cffi и без мёртвых free-прокси
"""

import os
import re
import traceback
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# ---------- ENV ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
FULL_COOKIE = os.environ.get("FULL_COOKIE", "").strip()
CLUB_SLUG = os.environ.get("CLUB_SLUG", "utinoe-bratstvo").strip()
RUN_KEY = os.environ.get("RUN_KEY", "duck2026").strip()
PROXY = os.environ.get("PROXY", "").strip()  # опционально: http://ip:port

BASE = "https://mangabuff.ru"
BOOST_URL = f"{BASE}/clubs/{CLUB_SLUG}/boost"
HISTORY_URL = f"{BASE}/clubs/{CLUB_SLUG}/history"
MSK = ZoneInfo("Europe/Moscow")


def now_msk() -> str:
    return datetime.now(MSK).strftime("%d.%m.%Y %H:%M МСК")


def tg_send(text: str, chat_id: str | None = None) -> None:
    chat = str(chat_id or CHAT_ID).strip()
    if not BOT_TOKEN or not chat:
        print("WARN: no BOT_TOKEN/CHAT_ID", flush=True)
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=40,
        )
        if r.status_code != 200:
            print("TG fail:", r.status_code, r.text[:300], flush=True)
    except Exception as e:
        print("TG exception:", e, flush=True)


def die(where: str, detail: str = "") -> None:
    msg = (
        "Извините пожалуйста, но я <b>обосрался</b> 💩\n"
        f"<b>Где:</b> {escape(str(where))}\n"
        f"<b>Detail:</b> <code>{escape(str(detail)[:1400])}</code>\n"
        "я головой бился об крышу унитаза вместо того чтобы работать как надо"
    )
    tg_send(msg)
    print(f"DIE [{where}] {detail}", flush=True)
    raise SystemExit(str(detail)[:400] or "1")


def browser_headers() -> dict:
    h = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Referer": f"{BASE}/clubs/{CLUB_SLUG}",
        "Origin": BASE,
    }
    if FULL_COOKIE:
        h["Cookie"] = FULL_COOKIE
    return h


def fetch(url: str) -> str:
    """Прямой запрос + Session + cookie. PROXY только если ты сам задал в env."""
    session = requests.Session()
    h = browser_headers()
    proxies = None
    if PROXY:
        p = PROXY if "://" in PROXY else f"http://{PROXY}"
        proxies = {"http": p, "https": p}

    last = ""
    for attempt in range(2):
        try:
            r = session.get(
                url,
                headers=h,
                proxies=proxies,
                timeout=30,
                allow_redirects=True,
            )
            text = r.text or ""
            low = text.lower()
            if r.status_code == 200 and "ddos" not in low and len(text) > 1500:
                print(f"fetch OK attempt={attempt} len={len(text)}", flush=True)
                return text
            last = f"status={r.status_code} len={len(text)} ddos={'yes' if 'ddos' in low else 'no'}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            print("fetch err:", last, flush=True)

    die(
        "fetch",
        f"MangaBuff не отдал страницу. {last}\n"
        f"url={url}\n"
        "1) Обнови FULL_COOKIE (Cookie Manager, вся строка)\n"
        "2) Или задай PROXY=http://ip:port в Environment (живой residential)\n"
        "3) Free-прокси с интернета почти не работают против DDoS-Guard",
    )
    return ""


def parse_boost(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    seen = set()
    junk = {
        "главная", "каталог", "рейтинг", "подборки", "колоды",
        "лента", "клубы", "профиль", "новости", "меню",
    }
    rows = soup.select(
        "table tbody tr, table tr, "
        ".club-boosters-list tr, .boosters-table tr, "
        "[class*='booster'] tr, [class*='member'] tr, li"
    )
    for el in rows:
        a = el.select_one("a[href*='/users/'], a[href*='/user/']")
        if not a:
            continue
        name = (a.get_text(strip=True) or "").strip()
        if not name or name.lower() in junk:
            continue
        full = " ".join(el.get_text(" ", strip=True).split())
        m = re.search(r"(\d[\d\s]*)\s*$", full)
        if not m:
            continue
        score = re.sub(r"\D", "", m.group(1))
        key = name.lower()
        if not score or key in seen:
            continue
        seen.add(key)
        out.append((name, score))
        if len(out) >= 20:
            break
    return out


def parse_history(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for el in soup.select(
        ".club-history-list li, .history-table tr, "
        "[class*='history'] li, [class*='history'] tr, li, tr"
    ):
        t = " ".join(el.get_text(" ", strip=True).split())
        if 10 < len(t) < 200 and "главная" not in t.lower() and "каталог" not in t.lower():
            out.append(t)
            if len(out) >= 10:
                break
    return out


def format_top(title: str, rows: list) -> str:
    lines = [
        f"<b>{escape(title)}</b>",
        f"<i>{now_msk()}</i>",
        f"Клуб: <code>{escape(CLUB_SLUG)}</code>",
        "",
    ]
    if not rows:
        lines.append("⚠️ Пусто (никто не вносил / cookie / селектор / защита)")
        lines.append(f'\n<a href="{BOOST_URL}">открыть boost</a>')
        return "\n".join(lines)
    medals = ["🥇", "🥈", "🥉"]
    for i, (nick, score) in enumerate(rows[:20]):
        p = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{p} <b>{escape(nick)}</b> — <code>{escape(score)}</code>")
    lines.append(f'\n<a href="{BOOST_URL}">открыть boost</a>')
    return "\n".join(lines)


def format_history(rows: list) -> str:
    lines = [
        "<b>📜 Последние 10 кто внёс</b>",
        f"<i>{now_msk()}</i>",
        f"Клуб: <code>{escape(CLUB_SLUG)}</code>",
        "",
    ]
    if not rows:
        lines.append("⚠️ История пустая")
        lines.append(f'\n<a href="{HISTORY_URL}">история</a>')
        return "\n".join(lines)
    for i, t in enumerate(rows[:10], 1):
        lines.append(f"{i}. {escape(t)}")
    lines.append(f'\n<a href="{HISTORY_URL}">история</a>')
    return "\n".join(lines)


def run(mode: str = None, chat_id: str = None) -> str:
    mode = (mode or "all").lower().strip()
    target = chat_id or CHAT_ID

    print(f"=== RUN mode={mode} club={CLUB_SLUG} cookie_len={len(FULL_COOKIE)} proxy={bool(PROXY)} ===", flush=True)

    if not BOT_TOKEN or not CHAT_ID:
        die("config", "Нет BOT_TOKEN или CHAT_ID")
    if not FULL_COOKIE or len(FULL_COOKIE) < 50:
        die("config", "FULL_COOKIE пустой или слишком короткий. Обнови из Cookie Manager.")

    tg_send(f"⏳ Запуск <b>{escape(mode)}</b>… клуб <code>{escape(CLUB_SLUG)}</code>", target)

    period_map = {
        "day": "?period=day",
        "today": "?period=day",
        "now": "?period=day",
        "daily": "?period=day",
        "week": "?period=week",
        "weekly": "?period=week",
        "month": "?period=month",
        "all": "?period=all",
    }
    titles = {
        "day": "📅 Топ сегодня",
        "today": "📅 Топ сегодня",
        "now": "📅 Топ сегодня",
        "daily": "📅 Топ сегодня",
        "week": "🏆 Топ неделя",
        "weekly": "🏆 Топ неделя",
        "month": "📆 Топ месяц",
        "all": "📊 Топ (все время)",
    }

    try:
        if mode in period_map:
            html = fetch(BOOST_URL + period_map[mode])
            rows = parse_boost(html)
            tg_send(format_top(titles.get(mode, "📊 Топ"), rows), target)

        if mode in ("recent", "history", "all"):
            html = fetch(HISTORY_URL)
            items = parse_history(html)
            tg_send(format_history(items), target)

        tg_send("✅ Готово", target)
        return "ok"
    except SystemExit:
        raise
    except Exception as e:
        die("краш", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1000:]}")
        return "fail"
