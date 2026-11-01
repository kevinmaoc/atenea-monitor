#!/usr/bin/env python3
"""Vigila ateneaprofesional.com y avisa si aparece el calendario de adviento
u otros cambios (links nuevos en el home, páginas/colecciones/productos nuevos)."""
import json, os, re, sys, urllib.parse, urllib.request
from pathlib import Path

BASE = "https://ateneaprofesional.com"
STATE = Path(__file__).with_name("state.json")
KEYWORDS = ["adviento", "advent", "calendario de navidad", "advent calendar"]
UA = {"User-Agent": "Mozilla/5.0 (compatible; AteneaMonitor/1.0)"}

NTFY_TOPIC = os.getenv("NTFY_TOPIC")            # opción A (la más simple)
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")      # opción B
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def notify(title, msg):
    print(f"[ALERTA] {title}\n{msg}")
    if NTFY_TOPIC:
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"),
            headers={"Title": title.encode("utf-8").decode("latin-1", "ignore"),
                     "Priority": "high", "Click": BASE})
        urllib.request.urlopen(req, timeout=30)
    if TG_TOKEN and TG_CHAT:
        data = urllib.parse.urlencode(
            {"chat_id": TG_CHAT, "text": f"{title}\n\n{msg}"}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=30)


def home_links(html):
    links = set()
    for href in re.findall(r'href="([^"#]+)"', html):
        u = urllib.parse.urljoin(BASE + "/", href)
        p = urllib.parse.urlparse(u)
        if p.netloc.endswith("ateneaprofesional.com"):
            links.add(p.path.rstrip("/") or "/")
    return links


def sitemap_urls():
    urls = set()
    try:
        index = get(f"{BASE}/sitemap.xml")
    except Exception as e:
        print("sitemap no disponible:", e)
        return urls
    for sm in re.findall(r"<loc>([^<]+)</loc>", index):
        try:
            for u in re.findall(r"<loc>([^<]+)</loc>", get(sm.replace("&amp;", "&"))):
                urls.add(urllib.parse.urlparse(u).path.rstrip("/") or "/")
        except Exception as e:
            print("error en", sm, e)
    return urls


def main():
    html = get(BASE + "/")
    text = re.sub(r"<[^>]+>", " ", html).lower()
    now = {
        "links": sorted(home_links(html)),
        "sitemap": sorted(sitemap_urls()),
        "keyword_hits": sorted(k for k in KEYWORDS if k in text),
    }
    now["keyword_hits"] += sorted(
        {f"url:{u}" for u in now["links"] + now["sitemap"]
         if any(k.replace(" ", "-") in u.lower() for k in KEYWORDS)})

    if not STATE.exists():
        STATE.write_text(json.dumps(now, indent=1, ensure_ascii=False))
        notify("Monitor Atenea activo",
               f"Línea base guardada ({len(now['links'])} links, "
               f"{len(now['sitemap'])} URLs en sitemap). Te aviso si hay cambios.")
        return

    old = json.loads(STATE.read_text())
    alerts = []

    new_hits = set(now["keyword_hits"]) - set(old.get("keyword_hits", []))
    if new_hits:
        alerts.append("🎄 ¡Posible calendario de adviento! Detectado: " + ", ".join(sorted(new_hits)))

    new_links = set(now["links"]) - set(old["links"])
    if new_links:
        alerts.append("Links nuevos en el home:\n" + "\n".join(BASE + l for l in sorted(new_links)[:15]))

    new_sm = set(now["sitemap"]) - set(old.get("sitemap", []))
    if new_sm and old.get("sitemap"):
        alerts.append("Páginas/colecciones/productos nuevos:\n" + "\n".join(BASE + l for l in sorted(new_sm)[:15]))

    if alerts:
        notify("Cambios en Atenea Profesional", "\n\n".join(alerts))
        STATE.write_text(json.dumps(now, indent=1, ensure_ascii=False))
    else:
        print("Sin cambios.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
