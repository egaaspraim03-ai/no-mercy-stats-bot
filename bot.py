#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MangaBuff club stats → Telegram. Render-ready."""

from __future__ import annotations

import os
import re
import sys
import time
import traceback
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MangaBuff Telegram bot for Render. Обходит Cloudflare/DDoS-Guard через curl_cffi."""

from __future__ import annotations
import os, re, sys, time, traceback
from zoneinfo import ZoneInfo
from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except Exception:
    HAS_CFFI = False

try:
    import cloudscraper
    HAS_CS = True
except Exception:
    HAS_CS = False

# === ENV ===
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
FULL_COOKIE = os.environ.get("FULL_COOKIE", "").strip()
MODE = os.environ.get("MODE", "all").strip().lower()
PROXY = os.environ.get("PROXY", "").strip()
CLUB_SLUG = os.environ.get("CLUB_SLUG", "utinoe-bratstvo").strip()
CLUB_NAME = os.environ.get("CLUB_NAME", "Утиное Братство")
MSK = ZoneInfo("Europe/Moscow")

BASE = "https://mangabuff.ru"
BOOST_URL = f"{BASE}/clubs/{CLUB_SLUG}/boost"
HISTORY_URL = f"{BASE}/clubs/{CLUB_SLUG}/history"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

BAD = {"замен", "опыт", "сегодня", "доступно", "карт", "штраф", "бесплат", "платн", "правил", "войти", "регистр", "boost", "history"}

def now_msk():
    return datetime.now(MSK).strftime("%d.%m.%Y, %H:%M МСК")

def send_telegram(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("NO TOKEN/CHAT_ID", file=sys.stderr)
        return
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": CHAT_ID, "text": text[:4000], "parse_mode": "HTML"},
                          timeout=30)
    except Exception as e:
        print("tg fail", e, file=sys.stderr)

def die(where: str, detail: str = "") -> None:
    msg = f"Извините пожалуйста, но я <b>обосрался</b> 💩\n<b>Где:</b> <code>{where}</code>\n"
    if detail: msg += f"<b>Что:</b>\n<code>{detail[:2000]}</code>\n"
    msg += f"<i>{now_msk()}</i>\n<i>Render | proxy={'yes' if PROXY else 'no'} | slug={CLUB_SLUG}</i>"
    print(f"DIE {where}", file=sys.stderr)
    send_telegram(msg)
    raise SystemExit(1)

def headers():
    h = {"User-Agent": UA, "Cookie": FULL_COOKIE, "Referer": BOOST_URL, "Origin": BASE}
    if xsrf := xsrf_from_cookie():
        h["X-XSRF-TOKEN"] = xsrf
        h["X-Requested-With"] = "XMLHttpRequest"
    return h

def xsrf_from_cookie():
    m = re.search(r"XSRF-TOKEN=([^;]+)", FULL_COOKIE)
    return unquote(m.group(1)) if m else None

def proxies():
    return {"http": PROXY, "https": PROXY} if PROXY else None

def fetch(url: str):
    px = proxies()
    h = headers()
    for name, engine in [("curl_cffi", fetch_cffi), ("cloudscraper", fetch_cloudscraper)]:
        if not (HAS_CFFI if name == "curl_cffi" else HAS_CS): continue
        try:
            r = engine(url, headers=h, proxies=px, timeout=60)
            if r.status_code == 200:
                return r.text
            if "403" in str(r.status_code) or "ddos" in str(r.text).lower():
                die("Cloudflare/DDoS-Guard", f"{name} вернул {r.status_code}")
        except Exception as e:
            pass
    # fallback requests
    r = requests.get(url, headers=h, proxies=px, timeout=60)
    return r.text

def fetch_cffi(url, headers, proxies, timeout):
    return cffi_requests.get(url, headers=headers, proxies=proxies, timeout=timeout, impersonate="chrome131")

def fetch_cloudscraper(url, headers, proxies, timeout):
    s = cloudscraper.create_scraper()
    return s.get(url, headers=headers, proxies=proxies, timeout=timeout)

# === Парсеры (без изменений) ===
def parse_boost(html):
    # ... (твой старый parse_boost из предыдущего сообщения)
    pass  # вставь сюда свой

def parse_history(html):
    # ... (твой старый parse_history)
    pass

def format_top(title, rows):
    # ... (твой формат)

def format_history(items):
    # ... (твой формат)

def run(mode=None):
    mode = (mode or MODE or "all").lower()
    print("MODE", mode, "PROXY", bool(PROXY))
    # вызовы smart_fetch + send_telegram
    # ... (твой основной run logic)

if __name__ == "__main__":
    run()
