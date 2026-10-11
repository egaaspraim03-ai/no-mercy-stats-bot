#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MangaBuff Telegram Bot (интерактивный)
Команды: /all, /today, /week, /month, /recent
"""

import os
import re
import sys
import random
import traceback
from html import escape
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup
from flask import Flask, request

# ---------- ENV ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
FULL_COOKIE = os.environ.get("FULL_COOKIE", "").strip()
CLUB_SLUG = os.environ.get("CLUB_SLUG", "utinoe-bratstvo").strip()
PROXY = os.environ.get("PROXY", "").strip()

BASE = "https://mangabuff.ru"
BOOST_URL = f"{BASE}/clubs/{CLUB_SLUG}/boost"
HISTORY_URL = f"{BASE}/clubs/{CLUB_SLUG}/history"


# ---------- helpers ----------
def tg_send(text: str, chat_id: str = None) -> None:
    chat = chat_id or CHAT_ID
    if not chat: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=40)


def die(where: str, detail: str = "") -> None:
    msg = f"Извините пожалуйста, но я <b>обосрался</b> 💩\n<b>Где:</b> {escape(str(where))}\n<b>Detail:</b> <code>{escape(str(detail)[:1500])}</code>"
    tg_send(msg, CHAT_ID)
    raise SystemExit(f"{where}: {detail}")


def headers() -> dict:
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
         "Referer": f"{BASE}/clubs/{CLUB_SLUG}"}
    if FULL_COOKIE: h["Cookie"] = FULL_COOKIE
    return h


# ---------- proxies ----------
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
                    if p and not p.startswith("#") and ":" in p:
                        p = p.split()[0] if " " in p else p
                        lines.append({"ip": p, "proto": src["proto"]})
        except Exception: continue
    if lines: random.shuffle(lines); return lines
    return None


def fetch(url: str) -> str:
    h = headers()
    plist = (proxies() or [])[:8]
    user_agents = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"]

    if HAS_CFFI:  # оставил для совместимости
        try:
            r = cffi_requests.get(url, headers=h, proxies=None, timeout=20, impersonate="chrome131")
            if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
                return r.text
        except Exception: pass

    for pdata in plist:
        px = {"http": f"http://{pdata['ip']}", "https": f"http://{pdata['ip']}"}
        h["User-Agent"] = random.choice(user_agents)
        try:
            if HAS_CFFI:
                r = cffi_requests.get(url, headers=h, proxies=px, timeout=12, impersonate="chrome131")
            else:
                r = requests.get(url, headers=h, proxies=px, timeout=12)
            if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
                return r.text
        except Exception: continue

    die("fetch", "не удалось скачать страницу")
    return ""


# ---------- parsers ----------
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
        return f"<b>{escape(title)}</b>\nпусто 🤷‍♂️\n\n<a href=\"{BOOST_URL}\">открыть boost</a>"
    lines = [f"<b>{escape(title)}</b>", f"<i>клуб: {escape(CLUB_SLUG)}</i>", ""]
    for i, (nick, score) in enumerate(rows[:20]):
        lines.append(f"{i+1}. <b>{escape(nick)}</b> — <code>{score}</code>")
    lines.append(f"\n<a href=\"{BOOST_URL}\">открыть boost</a>")
    return "\n".join(lines)


def format_history(rows: list) -> str:
    if not rows:
        return f"<b>Последние 10 кто внёс</b>\nпусто 🤷‍♂️\n\n<a href=\"{HISTORY_URL}\">история</a>"
    lines = ["<b>Последние 10 кто внёс</b>", f"<i>клуб: {escape(CLUB_SLUG)}</i>", ""]
    for i, t in enumerate(rows[:10], 1):
        lines.append(f"{i}. {escape(t)}")
    lines.append(f"\n<a href=\"{HISTORY_URL}\">история</a>")
    return "\n".join(lines)


# ---------- run ----------
def run(mode: str = None, chat_id: str = None) -> None:
    mode = (mode or "all").lower()
    if not chat_id: die("config", "chat_id не передан")
    tg_send(f"⏳ Запуск <b>{escape(mode)}</b>… клуб <code>{escape(CLUB_SLUG)}</code>", chat_id)

    try:
        period_map = {"all": "?period=all", "day": "?period=day", "week": "?period=week", "month": "?period=month"}
        titles = {"all": "📊 Топ (все время)", "day": "📅 Топ сегодня", "week": "🏆 Топ неделя", "month": "📆 Топ месяц"}

        if mode in period_map:
            target_url = BOOST_URL + period_map[mode]
            html = fetch(target_url)
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


# ---------- Flask app ----------
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.json
    webhook(data)  # вызов функции
    return "", 200


@app.route("/health")
def health():
    return jsonify({"ok": True, "bot_loaded": True, "service": "no-mercy-stats-bot"})


# ---------- webhook функция ----------
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


# ---------- main ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
