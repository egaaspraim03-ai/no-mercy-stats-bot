
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MangaBuff club stats bot for Render (utinoe-bratstvo)
modes: all | now | week | recent
"""

import os
import re
import sys
import json
import random
import traceback
from datetime import datetime, timedelta
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
    """Юморная ошибка в Telegram + SystemExit"""
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
    """Cookie + browser-like headers"""
    h = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": f"{BASE}/clubs/{CLUB_SLUG}",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if FULL_COOKIE:
        h["Cookie"] = FULL_COOKIE
        # XSRF из cookie если есть
        m = re.search(r"XSRF-TOKEN=([^;]+)", FULL_COOKIE)
        if m:
            from urllib.parse import unquote
            h["X-XSRF-TOKEN"] = unquote(m.group(1))
    return h


# ---------- free proxies ----------
def proxies():
    """Список dict {ip, proto} или None"""
    if PROXY:
        p = PROXY.replace("http://", "").replace("https://", "").replace("socks5://", "")
        return [{"ip": p, "proto": "http"}]

    sources = [
        {
            "url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all",
            "proto": "http",
        },
        {
            "url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all",
            "proto": "socks5",
        },
        {
            "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "proto": "http",
        },
        {
            "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            "proto": "http",
        },
        {
            "url": "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            "proto": "http",
        },
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
    """Скачать страницу: free-прокси → curl_cffi → cloudscraper → direct"""
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

    # 1) free proxies
    for pdata in plist[:35]:
        p = pdata["ip"]
        proto = pdata["proto"]
        px = {"http": f"{proto}://{p}", "https": f"{proto}://{p}"}
        h["User-Agent"] = random.choice(user_agents)

        if HAS_CFFI:
            for imp in impersonates:
                try:
                    r = cffi_requests.get(
                        url,
                        headers=h,
                        proxies=px,
                        timeout=15,
                        impersonate=imp,
                        allow_redirects=True,
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

    # 2) direct
    h["User-Agent"] = random.choice(user_agents)
    px_single = {"http": PROXY, "https": PROXY} if PROXY else None

    if HAS_CFFI:
        try:
            r = cffi_requests.get(
                url, headers=h, proxies=px_single, timeout=22, impersonate="chrome131"
            )
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
        die("fetch", f"status={r.status_code} body_len={len(r.text)} (DDoS-Guard/Cloudflare?)")
    except Exception as e:
        die("fetch", f"requests: {type(e).__name__}: {e}")

    die("fetch", "все free-прокси + direct провалились")
    return ""


# ---------- parsers (адаптивные) ----------
def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def parse_boost(html: str) -> list:
    """
    Топ буста: [(nick, score), ...]
    Сайт меняется — несколько стратегий.
    """
    soup = BeautifulSoup(html, "lxml")
    rows = []

    # 1) таблицы
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) < 2:
                continue
            texts = [_clean(td.get_text(" ", strip=True)) for td in tds]
            # ищем ник + число
            nick = None
            score = None
            for t in texts:
                if re.fullmatch(r"\d[\d\s]*", t.replace(" ", "")):
                    score = int(re.sub(r"\D", "", t) or "0")
                elif len(t) > 1 and not re.fullmatch(r"[\d\s]+", t):
                    if nick is None:
                        nick = t
            if nick and score is not None and score > 0:
                rows.append((nick, score))

    # 2) div/list с ником и очками рядом
    if not rows:
        for el in soup.select("a, span, div, li"):
            txt = _clean(el.get_text(" ", strip=True))
            m = re.search(r"^(.{2,40}?)\s+(\d[\d\s]{0,12})$", txt)
            if m:
                nick, sc = m.group(1).strip(), int(re.sub(r"\D", "", m.group(2)) or "0")
                if sc > 0 and nick.lower() not in ("ник", "очки", "место", "rank"):
                    rows.append((nick, sc))

    # уникальные, топ-30
    seen = set()
    out = []
    for nick, sc in rows:
        key = nick.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((nick, sc))
        if len(out) >= 30:
            break
    return out


def parse_history(html: str) -> list:
    """
    Последние внесения: [(nick, card_or_action, time), ...]
    """
    soup = BeautifulSoup(html, "lxml")
    items = []

    # строки таблицы / list-item
    candidates = soup.select("tr, .history-item, .list-item, li, .card, .item")
    if not candidates:
        candidates = soup.find_all(["div", "li", "tr"])

    for el in candidates:
        txt = _clean(el.get_text(" ", strip=True))
        if len(txt) < 5 or len(txt) > 200:
            continue
        # пропуск мусора
        low = txt.lower()
        if any(x in low for x in ("правил", "замен", "cookie", "ddos", "cloudflare", "войти")):
            continue

        # ник — первая «словная» часть
        nick = None
        a = el.find("a")
        if a and a.get_text(strip=True):
            nick = _clean(a.get_text(strip=True))
        if not nick:
            parts = txt.split()
            if parts:
                nick = parts[0]

        if not nick or len(nick) < 2:
            continue

        items.append((nick, txt[:80], ""))
        if len(items) >= 25:
            break

    # уникальные ники, последние 10
    seen = set()
    out = []
    for nick, action, t in items:
        k = nick.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append((nick, action, t))
        if len(out) >= 10:
            break
    return out


# ---------- format ----------
MEDALS = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 31)]


def format_top(title: str, rows: list) -> str:
    if not rows:
        return f"<b>{escape(title)}</b>\nпусто 🤷‍♂️"
    lines = [f"<b>{escape(title)}</b>", f"<i>клуб:</i> {escape(CLUB_SLUG)}", ""]
    for i, (nick, score) in enumerate(rows[:20]):
        medal = MEDALS[i] if i < len(MEDALS) else f"{i+1}."
        lines.append(f"{medal} <b>{escape(nick)}</b> — <code>{score}</code>")
    lines.append("")
    lines.append(f"<a href=\"{BOOST_URL}\">открыть boost</a>")
    return "\n".join(lines)


def format_history(rows: list) -> str:
    if not rows:
        return "<b>Последние 10 внесений</b>\nпусто 🤷‍♂️"
    lines = ["<b>Последние 10 кто внёс</b>", f"<i>клуб:</i> {escape(CLUB_SLUG)}", ""]
    for i, (nick, action, _) in enumerate(rows[:10], 1):
        short = escape(action) if action and action != nick else ""
        if short and short.lower().startswith(nick.lower()):
            short = short[len(nick) :].strip(" —:-")
        lines.append(f"{i}. <b>{escape(nick)}</b>" + (f" — {short[:60]}" if short else ""))
    lines.append("")
    lines.append(f"<a href=\"{HISTORY_URL}\">история</a>")
    return "\n".join(lines)


# ---------- main API for app.py ----------
def run(mode: str = None) -> str:
    """
    mode: all | now | week | recent
    Вызывается из app.py /run?mode=...
    """
    mode = (mode or MODE_DEFAULT or "all").strip().lower()
    print(f"=== RUN mode={mode} club={CLUB_SLUG} cookie_len={len(FULL_COOKIE)} ===")

    if not BOT_TOKEN:
        die("config", "BOT_TOKEN пустой")
    if not CHAT_ID:
        die("config", "CHAT_ID пустой")
    if not FULL_COOKIE:
        die("config", "FULL_COOKIE пустой — обнови cookie с mangabuff.ru")

    messages = []

    try:
        if mode in ("all", "now", "day", "daily", "week", "weekly"):
            html_boost = fetch(BOOST_URL)
            top = parse_boost(html_boost)
            if mode in ("week", "weekly"):
                messages.append(format_top("🏆 Топ за неделю (boost)", top))
            elif mode in ("now", "day", "daily"):
                messages.append(format_top("📅 Топ за день / сейчас (boost)", top))
            else:
                messages.append(format_top("📅 Топ (boost) — день/общий", top))
                # второй блок как «неделя» тем же списком, если отдельной вкладки нет
                messages.append(format_top("🏆 Топ (boost) — неделя (тот же список, сайт может не делить)", top[:15]))

        if mode in ("all", "recent", "history", "now"):
            html_hist = fetch(HISTORY_URL)
            hist = parse_history(html_hist)
            messages.append(format_history(hist))

        if not messages:
            die("run", f"неизвестный mode={mode}")

        for m in messages:
            tg_send(m)

        print("OK sent", len(messages), "messages")
        return "ok"

    except SystemExit:
        raise
    except Exception as e:
        die("run", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}")


# local test
if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "all"
    run(m)
