#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import random
import traceback
from html import escape
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
FULL_COOKIE = os.environ.get("FULL_COOKIE", "").strip()
CLUB_SLUG = os.environ.get("CLUB_SLUG", "utinoe-bratstvo").strip()
PROXY = os.environ.get("PROXY", "").strip()

BASE = "https://mangabuff.ru"
BOOST_URL = f"{BASE}/clubs/{CLUB_SLUG}/boost"
HISTORY_URL = f"{BASE}/clubs/{CLUB_SLUG}/history"

def tg_send(text: str, chat_id: str = None) -> None:
    chat = chat_id or CHAT_ID
    if not chat: return
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": chat, "text": text, "parse_mode": "HTML"}, timeout=40)

def die(where: str, detail: str = "") -> None:
    tg_send(f"Извините пожалуйста, но я <b>обосрался</b> 💩\n<b>Где:</b> {escape(str(where))}\n<b>Detail:</b> <code>{escape(str(detail)[:1500])}</code>")
    raise SystemExit(f"{where}: {detail}")

def headers():
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"}
    if FULL_COOKIE: h["Cookie"] = FULL_COOKIE
    return h

def proxies():
    if PROXY:
        p = PROXY.replace("http://", "").replace("https://", "").replace("socks5://", "")
        return [{"ip": p, "proto": "http"}]
    sources = [
        {"url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000", "proto": "http"},
        {"url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000", "proto": "socks5"},
    ]
    lines = []
    for src in sources:
        try:
            r = requests.get(src["url"], timeout=12)
            if r.status_code == 200:
                for line in r.text.splitlines():
                    p = line.strip()
                    if p and ":" in p:
                        p = p.split()[0] if " " in p else p
                        lines.append({"ip": p, "proto": src["proto"]})
        except Exception: continue
    if lines: random.shuffle(lines); return lines
    return None

def fetch(url: str) -> str:
    h = headers()
    plist = (proxies() or [])[:8]
    for pdata in plist:
        px = {"http": f"http://{pdata['ip']}", "https": f"http://{pdata['ip']}"}
        h["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
        try:
            r = requests.get(url, headers=h, proxies=px, timeout=12)
            if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
                return r.text
        except Exception: continue
    die("fetch", "не удалось скачать страницу")
    return ""

def parse_boost(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    rows = soup.select("table tbody tr, .club-boosters-list tr, .boosters-table tr, [class*='booster'] tr")
    for el in rows:
        user_link = el.select_one("a[href*='/users/']")
        if not user_link: continue
        name = user_link.get_text(strip=True)
        if not name: continue
        full_text = " ".join(el.get_text(" ", strip=True).split())
        score_match = re.search(r"(\d+)[\s]*$", full_text)
        if score_match:
            score = score_match.group(1)
            if name.lower() not in ["главная", "каталог", "рейтинг", "подборки", "колоды"]:
                out.append((name, score))
                if len(out) >= 20: break
    return out

def parse_history(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    items = soup.select(".club-history-list li, .history-table tr, [class*='history'] li")
    for el in items:
        if el.select_one("a[href='/club']"): continue
        t = " ".join(el.get_text(" ", strip=True).split())
        if len(t) > 5 and len(t) < 180:
            out.append(t)
            if len(out) >= 10: break
    return out

def format_top(title: str, rows: list) -> str:
    if not rows:
        return f"<b>{title}</b>\nпусто 🤷‍♂️\n\n<a href=\"{BOOST_URL}\">открыть boost</a>"
    lines = [f"<b>{title}</b>", f"<i>клуб: {CLUB_SLUG}</i>", ""]
    for i, (nick, score) in enumerate(rows[:20]):
        lines.append(f"{i+1}. <b>{nick}</b> — <code>{score}</code>")
    lines.append(f"\n<a href=\"{BOOST_URL}\">открыть boost</a>")
    return "\n".join(lines)

def format_history(rows: list) -> str:
    if not rows:
        return f"<b>Последние 10 кто внёс</b>\nпусто 🤷‍♂️\n\n<a href=\"{HISTORY_URL}\">история</a>"
    lines = ["<b>Последние 10 кто внёс</b>", f"<i>клуб: {CLUB_SLUG}</i>", ""]
    for i, t in enumerate(rows[:10], 1):
        lines.append(f"{i}. {t}")
    lines.append(f"\n<a href=\"{HISTORY_URL}\">история</a>")
    return "\n".join(lines)

def run(mode: str = None, chat_id: str = None) -> None:
    mode = (mode or "all").lower()
    if not chat_id: die("config", "chat_id не передан")
    tg_send(f"⏳ Запуск <b>{mode}</b>… клуб <code>{CLUB_SLUG}</code>", chat_id)

    try:
        period_map = {"all": "?period=all", "day": "?period=day", "week": "?period=week", "month": "?period=month"}
        titles = {"all": "📊 Топ (все время)", "day": "📅 Топ сегодня", "week": "🏆 Топ неделя", "month": "📆 Топ месяц"}

        if mode in period_map:
            html = fetch(BOOST_URL + period_map[mode])
            rows = parse_boost(html)
            tg_send(format_top(titles[mode], rows), chat_id)

        if mode in ("recent", "history"):
            html = fetch(HISTORY_URL)
            items = parse_history(html)
            tg_send(format_history(items), chat_id)

        tg_send("✅ Готово! Результаты в этом же чате.", chat_id)

    except SystemExit:
        raise
    except Exception as e:
        die("краш", f"{type(e).__name__}: {e}")

def webhook(data):
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").lower()

    if not chat_id: return

    if text in ("/start", "/all"):
        run("all", chat_id)
    elif text in ("/today", "/day"):
        run("day", chat_id)
    elif text in ("/week"):
        run("week", chat_id)
    elif text in ("/month"):
        run("month", chat_id)
    elif text in ("/recent", "/history"):
        run("recent", chat_id)

if __name__ == "__main__":
    import sys
    m = sys.argv[1] if len(sys.argv) > 1 else "all"
    run(m)
