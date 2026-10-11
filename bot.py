#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MangaBuff bot for Render (free, исправленный под 3.14)"""

import os
import re
import sys
import traceback
from datetime import datetime
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

# === CONFIG ===
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
        return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": text[:4000], "parse_mode": "HTML"},
                      timeout=30)
    except Exception as e:
        print(f"tg fail: {e}", file=sys.stderr)

def die(where: str, detail: str = "") -> None:
    msg = f"Извините пожалуйста, но я <b>обосрался</b> 💩\n<b>Где:</b> <code>{where}</code>\n"
    if detail:
        msg += f"<b>Что:</b>\n<code>{detail[:2000]}</code>\n"
    msg += f"<i>{now_msk()}</i>\n<i>Render | proxy={'yes' if PROXY else 'no'}</i>"
    print(f"DIE {where}", file=sys.stderr)
    send_telegram(msg)
    raise SystemExit(1)

def headers():
    h = {
        "User-Agent": UA,
        "Cookie": FULL_COOKIE,
        "Referer": BOOST_URL,
        "Origin": BASE,
    }
    xs = xsrf_from_cookie()
    if xs:
        h["X-XSRF-TOKEN"] = xs
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
    for name, func in [
        ("curl_cffi", cffi_requests.get if HAS_CFFI else None),
        ("cloudscraper", cloudscraper.create_scraper().get if HAS_CS else None),
    ]:
        if func is None: continue
        try:
            r = func(url, headers=h, proxies=px, timeout=60)
            if r.status_code == 200:
                return r.text
            if r.status_code in (403, 429) or "ddos" in r.text.lower():
                die("Cloudflare/DDoS-Guard", f"{name} {r.status_code}")
        except Exception:
            pass
    r = requests.get(url, headers=h, proxies=px, timeout=60)
    return r.text

def parse_boost(html: str):
    soup = BeautifulSoup(html, "lxml")
    out = []
    seen = set()
    for el in soup.select("a[href*='/users/'], li, tr, [class*='member'], [class*='boost']"):
        text = " ".join(el.get_text(" ", strip=True).split())
        if not text or len(text) > 90: continue
        m = re.search(r"^(.+?)\s+(\d{1,7})$", text)
        if not m: continue
        name, score = m.group(1).strip(), m.group(2)
        low = name.lower()
        if any(b in low for b in BAD) or name in seen or name.isdigit(): continue
        if not re.search(r"[A-Za-zА-Яа-я]", name): continue
        seen.add(name)
        out.append((name, score))
        if len(out) >= 15: break
    return out

def parse_history(html: str):
    soup = BeautifulSoup(html, "lxml")
    out = []
    seen = set()
    for el in soup.select("li, tr, [class*='history'], [class*='log']"):
        t = " ".join(el.get_text(" ", strip=True).split())
        if not (8 < len(t) < 140) or t in seen: continue
        if "ddos" in t.lower(): continue
        seen.add(t)
        out.append(t)
        if len(out) >= 10: break
    return out

def format_top(title: str, rows):
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"<b>{title}</b>", f"<i>{now_msk()}</i>", f"Клуб: <b>{CLUB_NAME}</b>", ""]
    if not rows:
        lines.append("⚠️ Топ не найден")
    else:
        for i, (n, s) in enumerate(rows):
            p = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{p} <b>{n}</b> — {s}")
    return "\n".join(lines)

def format_history(items):
    lines = ["<b>📜 Последние вклады</b>", f"<i>{now_msk()}</i>", f"Клуб: <b>{CLUB_NAME}</b>", ""]
    if not items:
        lines.append("⚠️ История пустая")
    else:
        for i, t in enumerate(items, 1):
            lines.append(f"{i}. {t}")
    return "\n".join(lines)

def run(mode: str = None):
    mode = (mode or MODE or "all").lower()
    print(f"MODE={mode} | PROXY={'yes' if PROXY else 'no'} | cookie_len={len(FULL_COOKIE)}")
    if not BOT_TOKEN or not CHAT_ID:
        die("config", "Нет BOT_TOKEN или CHAT_ID")
    if not FULL_COOKIE or len(FULL_COOKIE) < 40:
        die("config", "FULL_COOKIE пустой")

    try:
        if mode in ("daily", "weekly", "all", "now"):
            html = fetch(BOOST_URL)
            rows = parse_boost(html)
            title = "📊 Топ (сутки)" if mode == "daily" else "📊 Топ (неделя)" if mode == "weekly" else "📊 Топ (сейчас)"
            send_telegram(format_top(title, rows))

        if mode in ("recent", "all", "history"):
            html = fetch(HISTORY_URL)
            items = parse_history(html)
            send_telegram(format_history(items))

        return 0
    except SystemExit:
        raise
    except Exception as e:
        die("краш", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}")
        return 1

if __name__ == "__main__":
    run()
