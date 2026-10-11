#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MangaBuff club stats bot for Render
modes: all | day | week | month | past_month | today | recent | history
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
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
FULL_COOKIE = os.environ.get("FULL_COOKIE", "").strip()
CLUB_SLUG = os.environ.get("CLUB_SLUG", "utinoe-bratstvo").strip() or "utinoe-bratstvo"
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
    print(f"DIE [{where}] {detail}", flush=True)
    raise SystemExit(f"{where}: {detail}"[:500])


def tg_send(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("WARN: BOT_TOKEN/CHAT_ID empty", flush=True)
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
        print("TG error:", r.status_code, r.text[:300], flush=True)


def headers() -> dict:
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
        m = re.search(r"XSRF-TOKEN=([^;]+)", FULL_COOKIE)
        if m:
            h["X-XSRF-TOKEN"] = unquote(m.group(1))
    return h


# ---------- free proxies ----------
def proxies():
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

    last_err = ""

    # free proxies
    for pdata in plist[:30]:
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
                        print(f"OK curl_cffi {imp} {proto}://{p}", flush=True)
                        return r.text
                    last_err = f"cffi {imp} {p}: {r.status_code}"
                except Exception as e:
                    last_err = f"cffi {p}: {type(e).__name__}: {e}"
                    continue

        if HAS_CS:
            try:
                s = cloudscraper.create_scraper()
                r = s.get(url, headers=h, proxies=px, timeout=15)
                if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
                    print(f"OK cloudscraper {proto}://{p}", flush=True)
                    return r.text
                last_err = f"cs {p}: {r.status_code}"
            except Exception as e:
                last_err = f"cs {p}: {type(e).__name__}: {e}"
                continue

    # direct
    h["User-Agent"] = random.choice(user_agents)
    px_single = {"http": PROXY, "https": PROXY} if PROXY else None

    if HAS_CFFI:
        try:
            r = cffi_requests.get(
                url, headers=h, proxies=px_single, timeout=22, impersonate="chrome131"
            )
            if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
                print("OK direct curl_cffi", flush=True)
                return r.text
            last_err = f"direct cffi: {r.status_code} len={len(r.text)}"
        except Exception as e:
            last_err = f"direct cffi: {type(e).__name__}: {e}"

    try:
        r = requests.get(url, headers=h, proxies=px_single, timeout=22)
        if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
            print("OK direct requests", flush=True)
            return r.text
        last_err = f"direct requests: status={r.status_code} len={len(r.text)}"
    except Exception as e:
        last_err = f"direct requests: {type(e).__name__}: {e}"

    die("fetch", last_err or "все free-прокси + direct провалились")
    return ""


# ---------- parsers ----------
def parse_boost(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    junk = {"главная", "каталог", "рейтинг", "подборки", "колоды", "комментарии",
            "рейтинг пользователей", "лента сайта", "популярное", "розыгрыши",
            "все карточки", "торговая площадка"}

    rows = soup.select(
        "table tbody tr, .club-boosters-list tr, .boosters-table tr, "
        "[class*='booster'] tr, [class*='ranking'] tr, [class*='rating'] tr"
    )
    if not rows:
        rows = soup.select(
            ".flex.items-center.justify-between, [class*='booster-row'], "
            "[class*='member'], [class*='user-row'], li"
        )

    for el in rows:
        user_link = el.select_one("a[href*='/users/'], a[href*='/user/']")
        if not user_link:
            continue

        name = user_link.get_text(strip=True)
        if not name or name.lower() in junk:
            continue

        full_text = " ".join(el.get_text(" ", strip=True).split())
        score_match = re.search(r"(\d[\d\s]*)\s*$", full_text)
        if not score_match:
            nums = re.findall(r"\d+", full_text)
            if not nums:
                continue
            score = nums[-1]
        else:
            score = re.sub(r"\D", "", score_match.group(1)) or "0"

        if not score.isdigit():
            continue

        out.append((name, score))
        if len(out) >= 20:
            break

    # fallback: any /users/ link near a number
    if not out:
        for a in soup.select("a[href*='/users/']"):
            name = a.get_text(strip=True)
            if not name or name.lower() in junk or len(name) < 2:
                continue
            parent = a.parent
            for _ in range(4):
                if parent is None:
                    break
                txt = " ".join(parent.get_text(" ", strip=True).split())
                m = re.search(r"(\d+)\s*$", txt)
                if m:
                    out.append((name, m.group(1)))
                    break
                parent = parent.parent
            if len(out) >= 15:
                break

    # unique by nick
    seen = set()
    uniq = []
    for nick, sc in out:
        k = nick.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append((nick, sc))
    return uniq


def parse_history(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    junk_sub = ("главная", "каталог", "рейтинг", "подборки", "колоды", "лента",
                "популярное", "розыгрыши", "карточки", "торговая", "комментари")

    items = soup.select(
        ".club-history-list li, .history-table tr, .club-log-item, "
        "[class*='history'] li, [class*='log'] li, [class*='history'] tr"
    )
    if not items:
        items = soup.select("table tbody tr, li")

    for el in items:
        if el.select_one("a[href='/club'], a[href='/clubs']"):
            continue

        user_link = el.select_one("a[href*='/users/'], a[href*='/user/']")
        t = " ".join(el.get_text(" ", strip=True).split())
        if not t or len(t) < 5 or len(t) > 180:
            continue
        low = t.lower()
        if any(j in low for j in junk_sub):
            continue

        if user_link:
            nick = user_link.get_text(strip=True)
            rest = t
            if nick and nick in t:
                rest = t.replace(nick, "", 1).strip(" —:-|")
            out.append(f"{nick} — {rest}" if rest else nick)
        else:
            out.append(t)

        if len(out) >= 10:
            break

    return out


def format_top(title: str, rows: list) -> str:
    if not rows:
        return f"<b>{escape(title)}</b>\nпусто 🤷‍♂️\n\n<a href=\"{BOOST_URL}\">открыть boost</a>"
    lines = [f"<b>{escape(title)}</b>", f"<i>клуб:</i> {escape(CLUB_SLUG)}", ""]
    for i, (nick, score) in enumerate(rows[:20]):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i + 1}."
        lines.append(f"{medal} <b>{escape(str(nick))}</b> — <code>{escape(str(score))}</code>")
    lines.append("")
    lines.append(f"<a href=\"{BOOST_URL}\">открыть boost</a>")
    return "\n".join(lines)


def format_history(rows: list) -> str:
    if not rows:
        return f"<b>Последние 10 кто внёс</b>\nпусто 🤷‍♂️\n\n<a href=\"{HISTORY_URL}\">история</a>"
    lines = ["<b>Последние 10 кто внёс</b>", f"<i>клуб:</i> {escape(CLUB_SLUG)}", ""]
    for i, t in enumerate(rows[:10], 1):
        lines.append(f"{i}. {escape(str(t))}")
    lines.append("")
    lines.append(f"<a href=\"{HISTORY_URL}\">история</a>")
    return "\n".join(lines)


# ---------- main API (app.py вызывает run) ----------
def run(mode: str = None) -> str:
    mode = (mode or MODE_DEFAULT or "all").strip().lower()
    print(f"=== RUN mode={mode} club={CLUB_SLUG} cookie_len={len(FULL_COOKIE)} ===", flush=True)

    if not BOT_TOKEN or not CHAT_ID:
        die("config", "Нет BOT_TOKEN или CHAT_ID")
    if not FULL_COOKIE or len(FULL_COOKIE) < 40:
        die("config", "FULL_COOKIE пустой или короткий — обнови cookie")

    try:
        period_map = {
            "all": "?period=all",
            "day": "?period=day",
            "today": "?period=day",
            "now": "?period=day",
            "daily": "?period=day",
            "week": "?period=week",
            "weekly": "?period=week",
            "month": "?period=month",
            "past_month": "?period=month",
        }

        titles = {
            "all": "📊 Топ (все время)",
            "day": "📅 Топ сегодня",
            "today": "📅 Топ сегодня",
            "now": "📅 Топ сегодня",
            "daily": "📅 Топ сегодня",
            "week": "🏆 Топ неделя",
            "weekly": "🏆 Топ неделя",
            "month": "📆 Топ месяц",
            "past_month": "📆 Топ прошлый месяц",
        }

        # boost periods
        if mode in period_map or mode in ("all", "day", "week", "month", "past_month", "today", "now", "daily", "weekly"):
            param = period_map.get(mode, "?period=all")
            target_url = BOOST_URL + param
            html = fetch(target_url)
            rows = parse_boost(html)
            title = titles.get(mode, "📊 Топ (boost)")
            tg_send(format_top(title, rows))

        # history / recent
        if mode in ("recent", "history", "all"):
            html_h = fetch(HISTORY_URL)
            items = parse_history(html_h)
            tg_send(format_history(items))

        if mode not in period_map and mode not in (
            "all", "day", "week", "month", "past_month", "today", "now",
            "daily", "weekly", "recent", "history"
        ):
            die("run", f"неизвестный mode={mode}")

        print("OK done", flush=True)
        return "ok"

    except SystemExit:
        raise
    except Exception as e:
        die("краш", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}")
        return "fail"


if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "all"
    run(m)
