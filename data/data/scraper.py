#!/usr/bin/env python3
"""KTM Tech Lab price scraper. Run: python scraper.py
A failed target never stops the run: the last known price is kept."""
import json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
from bs4 import BeautifulSoup

NPT = timezone(timedelta(hours=5, minutes=45))
OUT = Path("data/prices.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# REPLACE each url + selectors with a real product page and its CSS selectors
# (open the page in a desktop browser > right-click the price > Inspect).
TARGETS = [
    {"id": "m-redmi-note13", "category": "mobile", "store": "Sample Store A",
     "name": "Redmi Note 13 (8/128GB)", "specs": "6.67\" AMOLED | 108MP | 5000mAh",
     "url": "https://example.com/redmi-note-13", "title_selector": "h1", "price_selector": ".price",
     "fallback_price_npr": 28500},
    {"id": "m-galaxy-a15", "category": "mobile", "store": "Sample Store A",
     "name": "Samsung Galaxy A15 (6/128GB)", "specs": "6.5\" AMOLED | 50MP | 5000mAh",
     "url": "https://example.com/galaxy-a15", "title_selector": "h1", "price_selector": ".price",
     "fallback_price_npr": 25500},
    {"id": "m-realme-c67", "category": "mobile", "store": "Sample Store B",
     "name": "Realme C67 (8/128GB)", "specs": "6.72\" 90Hz | 108MP | 33W",
     "url": "https://example.com/realme-c67", "title_selector": "h1", "price_selector": ".price",
     "fallback_price_npr": 22500},
    {"id": "m-poco-x6", "category": "mobile", "store": "Sample Store B",
     "name": "POCO X6 5G (8/256GB)", "specs": "6.67\" AMOLED 120Hz | 64MP OIS | 67W",
     "url": "https://example.com/poco-x6", "title_selector": "h1", "price_selector": ".price",
     "fallback_price_npr": 41500},
    {"id": "l-hp15-r5", "category": "laptop", "store": "Sample Store A",
     "name": "HP 15 Ryzen 5 (16GB/512GB)", "specs": "15.6\" FHD | Ryzen 5 7520U | 16GB | 512GB SSD",
     "url": "https://example.com/hp-15-r5", "title_selector": "h1", "price_selector": ".price",
     "fallback_price_npr": 72000},
    {"id": "l-ideapad3-i5", "category": "laptop", "store": "Sample Store C",
     "name": "Lenovo IdeaPad Slim 3 i5 (16GB/512GB)", "specs": "15.6\" FHD | Core i5-12450H | 16GB | 512GB",
     "url": "https://example.com/ideapad-slim-3", "title_selector": "h1", "price_selector": ".price",
     "fallback_price_npr": 82000},
    {"id": "l-vivobook15-i3", "category": "laptop", "store": "Sample Store C",
     "name": "ASUS Vivobook 15 i3 (8GB/512GB)", "specs": "15.6\" FHD | Core i3-1215U | 8GB | 512GB",
     "url": "https://example.com/vivobook-15", "title_selector": "h1", "price_selector": ".price",
     "fallback_price_npr": 58500},
    {"id": "l-aspire5-r7", "category": "laptop", "store": "Sample Store B",
     "name": "Acer Aspire 5 Ryzen 7 (16GB/512GB)", "specs": "15.6\" FHD | Ryzen 7 5825U | 16GB | 512GB",
     "url": "https://example.com/aspire-5", "title_selector": "h1", "price_selector": ".price",
     "fallback_price_npr": 94500},
]


def parse_price(text):
    """'Rs. 45,999.00' -> 45999. Returns None if no sane price is found."""
    m = re.search(r"\d[\d,]*(?:\.\d+)?", text or "")
    if not m:
        return None
    value = int(float(m.group(0).replace(",", "")))
    return value if 1000 <= value <= 2_000_000 else None


def scrape(target):
    r = requests.get(target["url"], headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    title_el = soup.select_one(target["title_selector"])
    price_el = soup.select_one(target["price_selector"])
    if not title_el or not price_el:
        raise ValueError("selector not found (markup changed or page blocked)")
    price = parse_price(price_el.get_text(" ", strip=True))
    if price is None:
        raise ValueError("price could not be parsed")
    return title_el.get_text(" ", strip=True)[:120], price


def load_existing():
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    old_doc = load_existing()
    prev = {i["id"]: i for i in old_doc.get("items", []) if isinstance(i, dict) and "id" in i}
    items = []
    for t in TARGETS:
        old = prev.get(t["id"])
        item = dict(old) if old else {
            "id": t["id"], "price_npr": t["fallback_price_npr"],
            "previous_price_npr": None, "price_drop_npr": 0, "status": "seed"}
        item.update(category=t["category"], store=t["store"], name=t["name"],
                    specs=t.get("specs", ""), url=t["url"])
        try:
            title, price = scrape(t)
            if price != item["price_npr"]:
                item["previous_price_npr"] = item["price_npr"]
                item["price_drop_npr"] = max(0, item["price_npr"] - price)
                item["price_npr"] = price
            item["source_title"] = title
            item["status"] = "live"
        except Exception as e:  # keep last known price
            print(f"[skip] {t['id']}: {e}", file=sys.stderr)
            if item.get("status") == "live":
                item["status"] = "cached"
        items.append(item)

    if old_doc.get("items") == items:
        print("No price changes.")
        return
    doc = {
        "brand": "ktmtechlab.com",
        "last_updated": datetime.now(NPT).isoformat(timespec="seconds"),
        "last_updated_note": "Nepal Time (NPT, UTC+05:45)",
        "items": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    print(f"Wrote {len(items)} items.")


if __name__ == "__main__":
    main()
