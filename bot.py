#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MangaBuff club stats bot for Telegram + Render
Один файл: Flask + парсер + Telegram
Сервис: https://random-shadows.onrender.com
"""

import os
import re
import random
import traceback
import threading
from html import escape

import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify

# ===================== ENV =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
FULL_COOKIE = os.environ.get("FULL_COOKIE", "").strip()
CLUB_SLUG = (os.environ.get("CLUB_SLUG", "utinoe-bratstvo") or "utinoe-bratstvo").strip()
RUN_KEY = os.environ.get("RUN_KEY", "duck2026").strip()
PROXY = os.environ.get("PROXY", "").strip()
MODE_DEFAULT = os.environ.get("MODE", "all").strip().lower()

BASE = "https://mangabuff.ru"
BOOST_URL = f"{BASE}/clubs/{CLUB_SLUG}/boost"
HISTORY_URL = f"{BASE}/clubs/{CLUB_SLUG}/history"

# ===================== Flask =====================
app = Flask(__name__)


# ===================== Telegram =====================
def tg_send(text: str, chat_id: str = None) -> None:
    chat = str(chat_id or CHAT_ID).strip()
    if not BOT_TOKEN or not chat:
        print("WARN: BOT_TOKEN or CHAT_ID empty", flush=True)
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=40,
        )
        if r.status_code != 200:
            print("TG ERROR:", r.status_code, r.text[:500], flush=True)
    except Exception as e:
        print("TG EXCEPTION:", type(e).__name__, e, flush=True)


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
    raise SystemExit(str(detail)[:500] or "1")


# ===================== HTTP / MangaBuff =====================
def headers() -> dict:
    h = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Referer": f"{BASE}/clubs/{CLUB_SLUG}",
        "Connection": "keep-alive",
    }
    if FULL_COOKIE:
        h["Cookie"] = FULL_COOKIE
    return h


def load_free_proxies() -> list:
    if PROXY:
        p = PROXY.replace("http://", "").replace("https://", "").replace("socks5://", "").strip()
        return [p] if p else []
    sources = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=8000",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    ]
    out = []
    for src in sources:
        try:
            r = requests.get(src, timeout=10)
            if r.status_code != 200:
                continue
            for line in r.text.splitlines():
                p = line.strip().split()[0] if line.strip() else ""
                if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$", p):
                    out.append(p)
        except Exception:
            continue
    random.shuffle(out)
    return out


def fetch(url: str) -> str:
    h = headers()
    last = ""

    # 1) direct
    try:
        r = requests.get(url, headers=h, timeout=25)
        if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
            print("fetch OK direct", flush=True)
            return r.text
        last = f"direct status={r.status_code} len={len(r.text)}"
    except Exception as e:
        last = f"direct {type(e).__name__}: {e}"

    # 2) free proxies
    for p in load_free_proxies()[:8]:
        try:
            r = requests.get(
                url,
                headers=h,
                proxies={"http": f"http://{p}", "https": f"http://{p}"},
                timeout=12,
            )
            if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 1500:
                print("fetch OK proxy", p, flush=True)
                return r.text
            last = f"proxy {p}: status={r.status_code}"
        except Exception as e:
            last = f"proxy {p}: {type(e).__name__}: {e}"
            continue

    die("fetch", last or "не удалось скачать страницу MangaBuff")
    return ""


# ===================== parsers =====================
def parse_boost(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    seen = set()
    junk = {
        "главная", "каталог", "рейтинг", "подборки", "колоды",
        "лента", "клубы", "профиль", "новости",
    }
    rows = soup.select(
        "table tbody tr, table tr, "
        ".club-boosters-list tr, .boosters-table tr, "
        "[class*='booster'] tr, [class*='member'] tr, li"
    )
    for el in rows:
        a = el.select_one("a[href*='/users/'], a[href*='/user/']")
        if not a:
            continue
        name = a.get_text(strip=True)
        if not name or name.lower() in junk:
            continue
        full = " ".join(el.get_text(" ", strip=True).split())
        m = re.search(r"(\d[\d\s]*)\s*$", full)
        if not m:
            continue
        score = re.sub(r"\D", "", m.group(1))
        key = name.lower()
        if not score or key in seen:
            continue
        seen.add(key)
        out.append((name, score))
        if len(out) >= 20:
            break
    return out


def parse_history(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for el in soup.select(
        ".club-history-list li, .history-table tr, "
        "[class*='history'] li, [class*='history'] tr, li, tr"
    ):
        t = " ".join(el.get_text(" ", strip=True).split())
        if 8 < len(t) < 180 and "главная" not in t.lower() and "каталог" not in t.lower():
            out.append(t)
            if len(out) >= 10:
                break
    return out


def format_top(title: str, rows: list) -> str:
    if not rows:
        return (
            f"<b>{escape(title)}</b>\n"
            f"<i>клуб:</i> {escape(CLUB_SLUG)}\n"
            "пусто 🤷‍♂️\n"
            f'<a href="{BOOST_URL}">открыть boost</a>'
        )
    lines = [f"<b>{escape(title)}</b>", f"<i>клуб:</i> {escape(CLUB_SLUG)}", ""]
    for i, (nick, score) in enumerate(rows[:20]):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i + 1}."
        lines.append(f"{medal} <b>{escape(nick)}</b> — <code>{escape(score)}</code>")
    lines.append(f'\n<a href="{BOOST_URL}">открыть boost</a>')
    return "\n".join(lines)


def format_history(rows: list) -> str:
    if not rows:
        return (
            f"<b>Последние 10 кто внёс</b>\n"
            f"<i>клуб:</i> {escape(CLUB_SLUG)}\n"
            "пусто 🤷‍♂️\n"
            f'<a href="{HISTORY_URL}">история</a>'
        )
    lines = ["<b>Последние 10 кто внёс</b>", f"<i>клуб:</i> {escape(CLUB_SLUG)}", ""]
    for i, t in enumerate(rows[:10], 1):
        lines.append(f"{i}. {escape(t)}")
    lines.append(f'\n<a href="{HISTORY_URL}">история</a>')
    return "\n".join(lines)


# ===================== run =====================
def run(mode: str = None) -> str:
    mode = (mode or MODE_DEFAULT or "all").lower()
    print(
        f"=== RUN mode={mode} club={CLUB_SLUG} cookie_len={len(FULL_COOKIE)} ===",
        flush=True,
    )
    if not BOT_TOKEN or not CHAT_ID:
        die("config", "Нет BOT_TOKEN или CHAT_ID")
    if not FULL_COOKIE or len(FULL_COOKIE) < 40:
        die("config", "FULL_COOKIE пустой или слишком короткий")

    tg_send(f"⏳ Запуск <b>{escape(mode)}</b>… клуб <code>{escape(CLUB_SLUG)}</code>")

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
            "past_month": "📆 Топ месяц",
        }

        if mode in period_map:
            html = fetch(BOOST_URL + period_map[mode])
            rows = parse_boost(html)
            tg_send(format_top(titles.get(mode, "📊 Топ"), rows))

        if mode in ("recent", "history", "all"):
            html = fetch(HISTORY_URL)
            items = parse_history(html)
            tg_send(format_history(items))

        tg_send("✅ Готово")
        return "ok"
    except SystemExit:
        raise
    except Exception as e:
        die("краш", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}")
        return "fail"


def _run_bg(mode: str) -> None:
    try:
        run(mode)
    except SystemExit:
        pass
    except Exception as e:
        try:
            tg_send(f"background crash: <code>{escape(str(e)[:800])}</code>")
        except Exception:
            pass


# ===================== routes =====================
@app.route("/")
@app.route("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "bot_loaded": True,
            "service": "random-shadows / no-mercy-stats-bot",
            "club": CLUB_SLUG,
            "token_set": bool(BOT_TOKEN),
            "chat_id_set": bool(CHAT_ID),
            "cookie_set": bool(FULL_COOKIE) and len(FULL_COOKIE) > 40,
            "cookie_len": len(FULL_COOKIE),
            "run_key_set": bool(RUN_KEY),
            "proxy_set": bool(PROXY),
            "error": None,
        }
    )


@app.route("/test-tg")
def test_tg():
    key = (request.args.get("key") or "").strip()
    if not RUN_KEY or key != RUN_KEY:
        return jsonify({"ok": False, "error": "bad key"}), 403
    try:
        tg_send("✅ Тест: бот жив, Telegram работает.")
        return jsonify({"ok": True, "msg": "sent test message"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/run")
def run_job():
    key = (request.args.get("key") or "").strip()
    mode = (request.args.get("mode") or "all").strip().lower()
    if not RUN_KEY or key != RUN_KEY:
        return jsonify({"ok": False, "error": "bad key"}), 403
    t = threading.Thread(target=_run_bg, args=(mode,), daemon=True)
    t.start()
    return jsonify(
        {
            "ok": True,
            "started": True,
            "mode": mode,
            "msg": "Работаю в фоне. Результат придёт в Telegram через 1–5 мин.",
        }
    )


# ===================== local =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
