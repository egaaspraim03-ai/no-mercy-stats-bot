#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MangaBuff club top → Telegram
GitHub Actions. 0₽.
Страницы: /boost и /history
"""

import os
import re
import sys
from datetime import datetime
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
FULL_COOKIE = os.environ.get("FULL_COOKIE", "").strip()
CLUB_SLUG = os.environ.get("CLUB_SLUG", "utinoe-bratstvo").strip()
MODE = os.environ.get("MODE", "weekly").strip().lower()  # daily | weekly | recent | all

BASE = "https://mangabuff.ru"
CLUB_NAME = "Утиное Братство"
MSK = ZoneInfo("Europe/Moscow")

UA = (
    "Mozilla/5.0 (Linux; Android 13; Mobile) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Mobile Safari/537.36"
)


def now_msk() -> str:
    return datetime.now(MSK).strftime("%d.%m.%Y, %H:%M МСК")


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"{BASE}/clubs/{CLUB_SLUG}/boost",
            "Origin": BASE,
        }
    )
    if FULL_COOKIE:
        s.headers["Cookie"] = FULL_COOKIE
        m = re.search(r"XSRF-TOKEN=([^;]+)", FULL_COOKIE)
        if m:
            s.headers["X-XSRF-TOKEN"] = unquote(m.group(1))
    return s


def fetch(url: str) -> str:
    s = session()
    r = s.get(url, timeout=45, allow_redirects=True)
    text = r.text or ""
    head = text[:800].lower()
    if r.status_code == 403 or "ddos-guard" in head or "ddos guard" in head:
        raise RuntimeError(
            f"403 / DDoS-Guard: {url} | status={r.status_code} len={len(text)}. "
            "Обнови FULL_COOKIE с телефона."
        )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} для {url}, len={len(text)}")
    if "/login" in (r.url or "") and "login" in head:
        raise RuntimeError("Редирект на login — cookie мёртвый, обнови FULL_COOKIE")
    return text


def parse_boost_top(html: str, limit: int = 15) -> list:
    soup = BeautifulSoup(html, "lxml")
    results = []
    seen = set()
    bad = (
        "замен", "опыт", "сегодня", "доступно", "карт", "владел",
        "штраф", "попыт", "бесплат", "платн", "неделя", "сутки", "месяц",
    )

    for el in soup.select(
        "a[href*='/users/'], .user-name, .nickname, "
        "[class*='member'], [class*='boost'], [class*='rating'], li, tr"
    ):
        text = " ".join(el.get_text(" ", strip=True).split())
        if not text or len(text) > 80:
            continue
        m = re.search(r"^(.+?)\s+(\d{1,6})$", text)
        if not m:
            continue
        name, score = m.group(1).strip(), m.group(2)
        low = name.lower()
        if any(b in low for b in bad):
            continue
        if name in seen or not re.search(r"[A-Za-zА-Яа-я]", name):
            continue
        seen.add(name)
        results.append((name, score))
        if len(results) >= limit:
            break

    if len(results) < 5:
        body = soup.get_text("\n", strip=True)
        for line in body.splitlines():
            line = " ".join(line.split())
            m = re.search(r"^([A-Za-zА-Яа-я0-9_ .\-]{2,40})\s+(\d{1,6})$", line)
            if not m:
                continue
            name, score = m.group(1).strip(), m.group(2)
            low = name.lower()
            if any(b in low for b in bad):
                continue
            if name in seen:
                continue
            seen.add(name)
            results.append((name, score))
            if len(results) >= limit:
                break

    return results[:limit]


def parse_history(html: str, limit: int = 10) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    seen = set()
    for el in soup.select(
        "li, tr, .history-item, [class*='history'], [class*='log'], [class*='contrib']"
    ):
        t = " ".join(el.get_text(" ", strip=True).split())
        if 8 < len(t) < 120 and t not in seen:
            if re.search(r"\d", t) or re.search(r"[A-Za-zА-Яа-я]{3,}", t):
                seen.add(t)
                out.append(t)
        if len(out) >= limit:
            break
    return out[:limit]


def format_top(title: str, rows: list) -> str:
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        f"<b>{title}</b>",
        f"<i>{now_msk()}</i>",
        f"Клуб: <b>{CLUB_NAME}</b>",
        "Источник: /boost",
        "",
    ]
    if not rows:
        lines.append("⚠️ Не удалось разобрать топ (структура сайта или cookie).")
        return "\n".join(lines)
    for i, (name, score) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{prefix} <b>{name}</b> — {score}")
    return "\n".join(lines)


def format_history(lines: list) -> str:
    out = [
        "<b>📜 Последние вклады</b>",
        f"<i>{now_msk()}</i>",
        f"Клуб: <b>{CLUB_NAME}</b>",
        "Источник: /history",
        "",
    ]
    if not lines:
        out.append("⚠️ История пуста или не распарсилась.")
    else:
        for i, t in enumerate(lines, 1):
            out.append(f"{i}. {t}")
    return "\n".join(out)


def send_telegram(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("Нет BOT_TOKEN или CHAT_ID")
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
    if not r.ok:
        raise RuntimeError(f"Telegram error: {r.status_code} {r.text[:300]}")


def main() -> int:
    print(f"MODE={MODE} CLUB={CLUB_SLUG} cookie_len={len(FULL_COOKIE)}")
    boost_url = f"{BASE}/clubs/{CLUB_SLUG}/boost"
    history_url = f"{BASE}/clubs/{CLUB_SLUG}/history"

    try:
        if MODE in ("daily", "all"):
            html = fetch(boost_url)
            rows = parse_boost_top(html)
            send_telegram(format_top("📊 Топ за сутки (boost)", rows))
            print(f"daily sent, rows={len(rows)}")

        if MODE in ("weekly", "all"):
            html = fetch(boost_url)
            rows = parse_boost_top(html)
            send_telegram(format_top("📊 Топ за неделю (boost)", rows))
            print(f"weekly sent, rows={len(rows)}")

        if MODE in ("recent", "all"):
            html = fetch(history_url)
            hist = parse_history(html)
            send_telegram(format_history(hist))
            print(f"recent sent, lines={len(hist)}")

        if MODE not in ("daily", "weekly", "recent", "all"):
            print("Unknown MODE: daily|weekly|recent|all", file=sys.stderr)
            return 1
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        try:
            send_telegram(f"❌ MangaBuff bot error\n<code>{e}</code>")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
