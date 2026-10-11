import random
import re

def proxies():
    if PROXY:
        return [{"ip": PROXY.replace("http://", "").replace("https://", "").replace("socks5://", ""), "proto": "http"}]

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


def fetch(url: str):
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

    # Уровень 1: free proxies
    for pdata in plist[:40]:
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
                    if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 2000:
                        print(f"✅ OK curl_cffi {imp} {proto}://{p}")
                        return r.text
                except Exception:
                    continue

        if HAS_CS:
            try:
                s = cloudscraper.create_scraper()
                r = s.get(url, headers=h, proxies=px, timeout=15)
                if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 2000:
                    print(f"✅ OK cloudscraper {proto}://{p}")
                    return r.text
            except Exception:
                continue

    # Уровень 2: direct
    h["User-Agent"] = random.choice(user_agents)
    px_single = {"http": PROXY, "https": PROXY} if PROXY else None
    if HAS_CFFI:
        try:
            r = cffi_requests.get(url, headers=h, proxies=px_single, timeout=20, impersonate="chrome131")
            if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 2000:
                return r.text
        except Exception:
            pass
    try:
        r = requests.get(url, headers=h, proxies=px_single, timeout=20)
        if r.status_code == 200 and "ddos" not in r.text.lower() and len(r.text) > 2000:
            return r.text
    except Exception:
        pass

    die(
        "fetch",
        "DDoS-Guard/Cloudflare: все free-прокси + direct дали 403. "
        "Бесплатные IP с Render почти не проходят MangaBuff."
    )
    return ""
