#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MangaBuff club stats bot for Render
modes: all | day | week | month | past_month | today | recent | history
"""

import os
import re
import sys
import json
import random
import traceback
from datetime import datetime
from html import escape

import requests
from bs4 import BeautifulSoup

# optional engines
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
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
FULL_COOKIE = os.environ.get("FULL_COOKIE", "").strip()
CLUB_SLUG = os.environ.get("CLUB_SLUG", "utinoe-bratstvo").strip()
PROXY = os.environ.get("PROXY", "").strip()
MODE_DEFAULT = os.environ.get("MODE", "all").strip().lower()

BASE = "https://mangabuff.ru"
BOOST_URL = f"{BASE}/clubs/{CLUB_SLUG}/boost"
HISTORY_URL = f"{BASE}/clubs/{CLUB_SLUG}/history"


# ---------- helpers ----------
def die(where: str, detail: str = "") -> None:
    msg = (
        "Извините пожалуйста, но я <b>обосрался</b> 💩\n"
        f"<b>Где:</b> {escape(str(where))}\n"
        f"<b>Detail:</b> <code>{escape(str(detail)[:1500])}</code>\n"
        "я головой бился об крышу унитаза вместо того чтобы работать как надо"
    )
    try:
        tg_send(msg)
    except Exception:
        pass
    print(f"DIE [{where}] {detail}", file=sys.stderr)
    raise SystemExit(1)


def tg_send(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("WARN: BOT_TOKEN/CHAT_ID empty, skip TG")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    if r.status_code != 200:
        print("TG error:", r.status_code, r.text[:300])


def headers() -> dict:
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": f"{BASE}/clubs/{CLUB_SLUG}",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if FULL_COOKIE:
        h["Cookie"] = FULL_COOKIE
        m = re.search(r"XSRF-TOKEN=([^;]+)", FULL_COOKIE)
        if m:
            from urllib.parse import unquote
            h["X-XSRF-TOKEN"] = unquote(m.group(1))
    return h


# ---------- free proxies ----------
def proxies():
    if PROXY:
        p = PROXY.replace("http://", "").replace("https://", "").replace("socks5://", "")
        return [{"ip": p, "proto": "http"}]

    sources = [
        {"url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all", "proto": "http"},
        {"url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all", "proto": "socks5"},
        {"url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt", "proto": "http"},
        {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt", "proto": "http"},
        {"url": "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt", "proto": "http"},
    ]

    lines = []
    seen = set()
    for src in sources:
        try:
            r = requests.get(src["url"], timeout=12)
            if r.status_code != 200:
                continue
            for line in r.text.splitlines():
                p = line.strip()
                if not p or p.startswith("#"):
                    continue
                p = p.replace("socks5://", "").replace("http://", "").replace("https://", "")
                p = p.split()[0] if " " in p else p
                if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$", p) and p not in seen:
                    seen.add(p)
                    lines.append({"ip": p, "proto": src["proto"]})
        except Exception:
            continue

    if lines:
        random.shuffle(lines)
        return lines
    return None


def fetch(url: str) -> str:
    h = headers()
    plist = proxies() or []

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    ]
    impersonates = ["chrome131", "chrome124", "chrome120", "chrome"]

    # free proxies
    for pdata in plist[:35]:
        p = pdata["ip"]
        proto = pdata["proto"]
        px = {"http": f"{proto}://{p}", "https": f"{proto}://{p}"}
        h["User-Agent"] = random.choice(user_agents)

        if HAS_CFFI:
            for imp in impersonates:
                try:
                    r = cffi_requests.get(
                        url, headers=h, proxies=px, timeout=15,
                        impersonate=imp, allow_redirects=True
                    )
                    if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
                        print(f"✅ OK curl_cffi {imp} {proto}://{p}")
                        return r.text
                except Exception:
                    continue

        if HAS_CS:
            try:
                s = cloudscraper.create_scraper()
                r = s.get(url, headers=h, proxies=px, timeout=15)
                if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
                    print(f"✅ OK cloudscraper {proto}://{p}")
                    return r.text
            except Exception:
                continue

    # direct
    h["User-Agent"] = random.choice(user_agents)
    px_single = {"http": PROXY, "https": PROXY} if PROXY else None

    if HAS_CFFI:
        try:
            r = cffi_requests.get(url, headers=h, proxies=px_single, timeout=22, impersonate="chrome131")
            if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
                print("✅ OK direct curl_cffi")
                return r.text
        except Exception as e:
            print("direct cffi fail:", e)

    try:
        r = requests.get(url, headers=h, proxies=px_single, timeout=22)
        if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
            print("✅ OK direct requests")
            return r.text
        die("fetch", f"status={r.status_code} body_len={len(r.text)}")
    except Exception as e:
        die("fetch", f"requests: {type(e).__name__}: {e}")

    die("fetch", "все free-прокси + direct провалились")
    return ""


# ---------- parsers (точные селекторы) ----------
def parse_boost(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []

    rows = soup.select("table tbody tr, .club-boosters-list tr, .boosters-table tr")
    if not rows:
        rows = soup.select(".flex.items-center.justify-between, [class*='booster-row']")

    for el in rows:
        user_link = el.select_one("a[href*='/users/']")
        if not user_link:
            continue

        name = user_link.get_text(strip=True)
        full_text = " ".join(el.get_text(" ", strip=True).split())
        score_match = re.search(r"(\d+)[\s]*$", full_text)

        if score_match and name:
            score = score_match.group(1)
            if name.lower() in ["главная", "каталог", "рейтинг", "подборки", "колоды"]:
                continue
            out.append((name, score))
            if len(out) >= 15:
                break

    return out


def parse_history(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []

    items = soup.select(".club-history-list li, .history-table tr, .club-log-item")
    if not items:
        items = soup.select("table tbody tr")

    for el in items:
        if el.select_one("a[href='/club']") or el.select_one("a[href='/clubs']"):
            continue

        t = " ".join(el.get_text(" ", strip=True).split())
        if not t or len(t) < 10 or len(t) > 150:
            continue
        if "главная" in t.lower() or "каталог" in t.lower():
            continue

        out.append(t)
        if len(out) >= 10:
            break

    return out


def format_top(title: str, rows: list) -> str:
    if not rows:
        return f"<b>{escape(title)}</b>\nпусто 🤷‍♂️"
    lines = [f"<b>{escape(title)}</b>", f"<i>клуб:</i> {escape(CLUB_SLUG)}", ""]
    for i, (nick, score) in enumerate(rows[:20]):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} <b>{escape(nick)}</b> — <code>{score}</code>")
    lines.append("")
    lines.append(f"<a href=\"{BOOST_URL}\">открыть boost</a>")
    return "\n".join(lines)


def format_history(rows: list) -> str:
    if not rows:
        return "<b>Последние 10 кто внёс</b>\nпусто 🤷‍♂️"
    lines = ["<b>Последние 10 кто внёс</b>", f"<i>клуб:</i> {escape(CLUB_SLUG)}", ""]
    for i, t in enumerate(rows[:10], 1):
        lines.append(f"{i}. {escape(t)}")
    lines.append("")
    lines.append(f"<a href=\"{HISTORY_URL}\">история</a>")
    return "\n".join(lines)


# ---------- main ----------
def run(mode: str = None) -> str:
    mode = (mode or MODE_DEFAULT or "all").lower()
    print(f"=== RUN mode={mode} club={CLUB_SLUG} ===")

    if not BOT_TOKEN or not CHAT_ID:
        die("config", "Нет BOT_TOKEN или CHAT_ID")
    if not FULL_COOKIE or len(FULL_COOKIE) < 40:
        die("config", "FULL_COOKIE пустой")

    try:
        period_map = {
            "all": "?period=all",
            "day": "?period=day",
            "today": "?period=day",
            "week": "?period=week",
            "weekly": "?period=week",
            "month": "?period=month",
            "past_month": "?period=month",
        }

        param = period_map.get(mode, "?period=all")
        target_url = BOOST_URL + param

        html = fetch(target_url)
        rows = parse_boost(html)

        titles = {
            "all": "📊 Топ (все время)",
            "day": "📅 Топ сегодня",
            "today": "📅 Топ сегодня",
            "week": "🏆 Топ неделя",
            "weekly": "🏆 Топ неделя",
            "month": "📆 Топ месяц",
            "past_month": "📆 Топ прошлый месяц"
        }

        title = titles.get(mode, titles["all"])
        tg_send(format_top(title, rows))

        return 0
    except SystemExit:
        raise
    except Exception as e:
        die("краш", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}")
        return 1


# local test
if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "all"
    run(m)
