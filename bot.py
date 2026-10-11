#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MangaBuff club stats → Telegram. Render-ready."""

from __future__ import annotations

import os
import re
import sys
import time
import traceback
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import unquote
from zoneinfo import ZoneInfo

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

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
FULL_COOKIE = os.environ.get("FULL_COOKIE", "").strip()
MODE = os.environ.get("MODE", "all").strip().lower()
PROXY = os.environ.get("PROXY", "").strip()  # http://user:pass@host:port
RUN_KEY = os.environ.get("RUN_KEY", "").strip()  # секрет для /run

_raw = os.environ.get("CLUB_SLUG", "utinoe-bratstvo").strip().rstrip("/")
if "mangabuff.ru" in _raw or "/" in _raw:
    m = re.search(r"clubs/([^/?#]+)", _raw)
    CLUB_SLUG = m.group(1) if m else _raw.split("/")[-1]
else:
    CLUB_SLUG = _raw or "utinoe-bratstvo"

BASE = "https://mangabuff.ru"
BOOST_URL = f"{BASE}/clubs/{CLUB_SLUG}/boost"
HISTORY_URL = f"{BASE}/clubs/{CLUB_SLUG}/history"
CLUB_NAME = os.environ.get("CLUB_NAME", "Утиное Братство")
MSK = ZoneInfo("Europe/Moscow")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

BAD = (
    "замен", "опыт", "сегодня", "доступно", "карт", "штраф", "бесплат", "платн",
    "неделя", "сутки", "месяц", "правил", "клуб", "boost", "history", "войти", "регистр",
)


def now_msk() -> str:
    return datetime.now(MSK).strftime("%d.%m.%Y, %H:%M МСК")


def send_telegram(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("NO BOT_TOKEN/CHAT_ID", file=sys.stderr)
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text[:4000],
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        print("tg", r.status_code, r.text[:200])
    except Exception as e:
        print("tg fail", e, file=sys.stderr)


def die(where: str, detail: str = "", code: int = 1) -> None:
    msg = (
        "Извините пожалуйста, но я <b>обосрался</b> 💩\n"
        f"<b>Где:</b> <code>{where}</code>\n"
    )
    if detail:
        msg += f"<b>Что случилось:</b>\n<code>{detail[:2800]}</code>\n"
    msg += (
        "\n<i>Я головой бился об крышу унитаза вместо того, "
        "чтобы работать как надо.</i>\n"
        f"<i>{now_msk()}</i>\n"
        f"<i>Render | slug={CLUB_SLUG} | proxy={'yes' if PROXY else 'no'}</i>"
    )
    print(f"DIE [{where}] {detail}", file=sys.stderr)
    send_telegram(msg)
    raise SystemExit(code)


def xsrf() -> Optional[str]:
    m = re.search(r"(?:^|;\s*)XSRF-TOKEN=([^;]+)", FULL_COOKIE or "")
    return unquote(m.group(1)) if m else None


def headers() -> dict:
    h = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
        "Referer": BOOST_URL,
        "Origin": BASE,
        "Cookie": FULL_COOKIE,
    }
    t = xsrf()
    if t:
        h["X-XSRF-TOKEN"] = t
        h["X-Requested-With"] = "XMLHttpRequest"
    return h


def proxies() -> Optional[dict]:
    if not PROXY:
        return None
    return {"http": PROXY, "https": PROXY}


def check_error(status: int, text: str, final_url: str) -> Optional[str]:
    head = (text or "")[:2000].lower()
    if status == 403 or "ddos-guard" in head or "ddos guard" in head:
        return "DDoS-Guard 403 (IP Render без residential PROXY почти всегда режется)"
    if status == 429:
        return "429 Too Many Requests"
    if status != 200:
        return f"HTTP {status}"
    if "/login" in (final_url or "") or ("войти" in head and "login" in head):
        return "Cookie мёртвый (redirect login) — обнови FULL_COOKIE"
    if "captcha" in head or "challenge" in head:
        return "Challenge/CAPTCHA"
    return None


def fetch_one(url: str) -> Tuple[str, List[str]]:
    errors: List[str] = []
    px = proxies()
    h = headers()

    # 1) curl_cffi
    if HAS_CFFI:
        try:
            r = cffi_requests.get(
                url,
                headers=h,
                proxies=px,
                timeout=60,
                allow_redirects=True,
                impersonate="chrome131",
            )
            err = check_error(r.status_code, r.text or "", str(getattr(r, "url", url)))
            if not err:
                return r.text or "", []
            errors.append(f"curl_cffi: {err}")
        except Exception as e:
            errors.append(f"curl_cffi: {type(e).__name__}: {e}")

    # 2) cloudscraper
    if HAS_CS:
        try:
            s = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
            r = s.get(url, headers=h, proxies=px, timeout=60, allow_redirects=True)
            err = check_error(r.status_code, r.text or "", str(getattr(r, "url", url)))
            if not err:
                return r.text or "", []
            errors.append(f"cloudscraper: {err}")
        except Exception as e:
            errors.append(f"cloudscraper: {type(e).__name__}: {e}")

    # 3) requests
    try:
        r = requests.get(url, headers=h, proxies=px, timeout=60, allow_redirects=True)
        err = check_error(r.status_code, r.text or "", str(getattr(r, "url", url)))
        if not err:
            return r.text or "", []
        errors.append(f"requests: {err}")
    except Exception as e:
        errors.append(f"requests: {type(e).__name__}: {e}")

    return "", errors


def smart_fetch(url: str, where: str) -> str:
    html, errors = fetch_one(url)
    if html:
        print("OK", where, "len", len(html))
        return html
    die(
        where,
        f"url={url}\ncookie_len={len(FULL_COOKIE)}\nproxy={'set' if PROXY else 'EMPTY — freе Render = 403'}\n"
        + "\n".join(errors[-12:]),
    )
    return ""


def parse_boost(html: str, limit: int = 15) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    out: List[Tuple[str, str]] = []
    seen = set()
    for el in soup.select(
        "a[href*='/users/'], li, tr, [class*='member'], [class*='boost'], "
        "[class*='top'], [class*='rating'], [class*='contrib']"
    ):
        text = " ".join(el.get_text(" ", strip=True).split())
        if not text or len(text) > 90:
            continue
        m = re.search(r"^(.+?)\s+(\d{1,7})$", text)
        if not m:
            continue
        name, score = m.group(1).strip(), m.group(2)
        low = name.lower()
        if any(b in low for b in BAD) or name in seen or name.isdigit():
            continue
        if not re.search(r"[A-Za-zА-Яа-я]", name):
            continue
        seen.add(name)
        out.append((name, score))
        if len(out) >= limit:
            break
    return out


def parse_history(html: str, limit: int = 10) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    out: List[str] = []
    seen = set()
    for el in soup.select("li, tr, [class*='history'], [class*='log'], [class*='contrib']"):
        t = " ".join(el.get_text(" ", strip=True).split())
        if not (8 < len(t) < 140) or t in seen:
            continue
        if "ddos" in t.lower():
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= limit:
            break
    return out


def format_top(title: str, rows: List[Tuple[str, str]]) -> str:
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"<b>{title}</b>", f"<i>{now_msk()}</i>", f"Клуб: <b>{CLUB_NAME}</b>", ""]
    if not rows:
        lines.append("⚠️ Топ пустой — вёрстка/доступ")
    else:
        for i, (n, s) in enumerate(rows):
            p = medals[i] if i < 3 else f"{i + 1}."
            lines.append(f"{p} <b>{n}</b> — {s}")
    return "\n".join(lines)


def format_history(items: List[str]) -> str:
    lines = ["<b>📜 Последние вклады</b>", f"<i>{now_msk()}</i>", f"Клуб: <b>{CLUB_NAME}</b>", ""]
    if not items:
        lines.append("⚠️ История пустая")
    else:
        for i, t in enumerate(items, 1):
            lines.append(f"{i}. {t}")
    return "\n".join(lines)


def run(mode: Optional[str] = None) -> int:
    mode = (mode or MODE or "all").lower()
    print("=" * 40)
    print("MODE", mode, "SLUG", CLUB_SLUG, "PROXY", bool(PROXY), "cffi", HAS_CFFI, "cs", HAS_CS)
    print("BOOST", BOOST_URL)
    print("=" * 40)

    if not BOT_TOKEN or not CHAT_ID:
        die("конфиг", "Нет BOT_TOKEN или CHAT_ID")
    if not FULL_COOKIE or len(FULL_COOKIE) < 40:
        die("конфиг", "FULL_COOKIE пустой/короткий")

    try:
        if mode in ("daily", "weekly", "all", "now"):
            html = smart_fetch(BOOST_URL, "загрузка /boost")
            rows = parse_boost(html)
            title = {
                "daily": "📊 Топ (сутки / boost)",
                "weekly": "📊 Топ (неделя / снимок boost)",
                "now": "📊 Топ (сейчас)",
                "all": "📊 Топ (boost)",
            }.get(mode, "📊 Топ (boost)")
            send_telegram(format_top(title, rows))
            if not rows:
                send_telegram(
                    "Извините пожалуйста, но я <b>частично обосрался</b> 💩\n"
                    "<b>Где:</b> <code>парсинг /boost</code>\n"
                    "Страницу открыл, топ не нашёл.\n"
                    "<i>Я головой бился об крышу унитаза вместо того, чтобы работать как надо.</i>"
                )

        if mode in ("recent", "all", "history"):
            html = smart_fetch(HISTORY_URL, "загрузка /history")
            items = parse_history(html)
            send_telegram(format_history(items))
            if not items:
                send_telegram(
                    "Извините пожалуйста, но я <b>частично обосрался</b> 💩\n"
                    "<b>Где:</b> <code>парсинг /history</code>\n"
                    "Страницу открыл, history пустая.\n"
                    "<i>Я головой бился об крышу унитаза вместо того, чтобы работать как надо.</i>"
                )

        if mode not in ("daily", "weekly", "recent", "all", "now", "history"):
            die("MODE", f"Неизвестный mode={mode}")
        return 0
    except SystemExit:
        raise
    except Exception as e:
        die("краш", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1800:]}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
