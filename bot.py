#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MangaBuff Telegram Bot (интерактивный)
Команды: /all, /today, /week, /month, /recent
Кнопки + постобработка + проверки
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

try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except Exception:
    HAS_CFFI = False
    cffi_requests = None

try:
    import cloudscraper
    HAS_CS = True
except Exception:
    HAS_CS = False

# ---------- ENV ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()  # только для теста, для реального — chat_id из сообщения
FULL_COOKIE = os.environ.get("FULL_COOKIE", "").strip()
CLUB_SLUG = os.environ.get("CLUB_SLUG", "utinoe-bratstvo").strip()
PROXY = os.environ.get("PROXY", "").strip()
MODE_DEFAULT = os.environ.get("MODE", "all").strip().lower()

BASE = "https://mangabuff.ru"
BOOST_URL = f"{BASE}/clubs/{CLUB_SLUG}/boost"
HISTORY_URL = f"{BASE}/clubs/{CLUB_SLUG}/history"


# ---------- helpers ----------
def tg_send(text: str, chat_id: str = None) -> None:
    chat = chat_id or CHAT_ID
    if not chat:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": chat,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=40,
    )
    if r.status_code != 200:
        print("TG error:", r.status_code, r.text[:300])


def die(where: str, detail: str = "") -> None:
    msg = (
        "Извините пожалуйста, но я <b>обосрался</b> 💩\n"
        f"<b>Где:</b> {escape(str(where))}\n"
        f"<b>Detail:</b> <code>{escape(str(detail)[:1500])}</code>\n"
        "я головой бился об крышу унитаза вместо того чтобы работать как надо"
    )
    tg_send(msg, CHAT_ID)
    raise SystemExit(f"{where}: {detail}")


def headers() -> dict:
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": f"{BASE}/clubs/{CLUB_SLUG}",
    }
    if FULL_COOKIE:
        h["Cookie"] = FULL_COOKIE
    return h


# ---------- free proxies + ускорение ----------
def proxies():
    if PROXY:
        p = PROXY.replace("http://", "").replace("https://", "").replace("socks5://", "")
        return [{"ip": p, "proto": "http"}]
    # ... (твой старый список источников) ...
    sources = [ ... ]  # оставь как было
    # (я оставил твой старый код, чтобы не дублировать)
    lines = []
    # ... логика ...
    if lines:
        random.shuffle(lines)
        return lines
    return None


def fetch(url: str) -> str:
    h = headers()
    plist = (proxies() or [])[:8]  # уменьшил до 8 — быстрее

    user_agents = [ ... ]  # твой список
    impersonates = ["chrome131", "chrome124"]

    last_err = ""

    # 1. Прямой запрос первым делом
    h["User-Agent"] = random.choice(user_agents)
    if HAS_CFFI:
        try:
            r = cffi_requests.get(url, headers=h, proxies=None, timeout=20, impersonate="chrome131")
            if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
                return r.text
        except Exception as e:
            last_err = str(e)

    # 2. Прокси
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
        except Exception:
            continue

    die("fetch", last_err or "не удалось скачать страницу")
    return ""


# ---------- парсеры (как раньше) ----------
def parse_boost(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    # ... (твой старый parse_boost) ...
    return out


def parse_history(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    # ... (твой старый parse_history) ...
    return out


def format_top(title: str, rows: list) -> str:
    # твой формат
    return "..."

def format_history(rows: list) -> str:
    # твой формат
    return "..."


# ---------- интерактивная логика ----------
def run(mode: str = None, chat_id: str = None) -> None:
    mode = (mode or MODE_DEFAULT or "all").lower()
    print(f"Запуск режима: {mode} (chat_id={chat_id})")

    if not chat_id:
        die("config", "chat_id не передан")

    tg_send(f"⏳ Запуск <b>{escape(mode)}</b>… клуб <code>{escape(CLUB_SLUG)}</code>\ncookie={len(FULL_COOKIE)}", chat_id)

    try:
        # ... весь твой старый код с period_map и fetch ...
        # (скопируй из предыдущей версии bot.py)

        if mode in ("all", "day", "week", "month", "past_month", "today", "now", "daily", "weekly"):
            # ... fetch boost, parse, tg_send ...

        if mode in ("recent", "history"):
            # ... history ...

        tg_send("✅ Готово!", chat_id)

    except SystemExit:
        raise
    except Exception as e:
        die("краш", f"{type(e).__name__}: {e}")


# ---------- WEBHOOK (Telegram) ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    message = data.get("message", {})

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").lower()

    if not chat_id:
        return "", 200

    # Команды
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

    return "", 200


if __name__ == "__main__":
    # Если запускаешь локально
    if len(sys.argv) > 1:
        run(sys.argv[1] if len(sys.argv) > 1 else "all")
    else:
        print("Бот запущен в режиме Telegram Webhook")
