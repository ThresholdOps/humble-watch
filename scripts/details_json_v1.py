#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ALL_JSON = DOCS / "all.json"
DETAILS_JSON = DOCS / "details.json"
MAX_BUNDLES = 80

@dataclass
class ScriptBlock:
    attrs: dict[str, str]
    text: str

class ScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[ScriptBlock] = []
        self._in_script = False
        self._attrs: dict[str, str] = {}
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script":
            self._in_script = True
            self._attrs = {k: v or "" for k, v in attrs}
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_script:
            self.scripts.append(ScriptBlock(self._attrs, "".join(self._parts)))
            self._in_script = False
            self._attrs = {}
            self._parts = []

def fetch_html(url: str) -> str:
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; humble-watch-details/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")

def extract_page_data(html: str) -> dict[str, Any]:
    parser = ScriptCollector()
    parser.feed(html)
    for script in parser.scripts:
        if script.attrs.get("id") == "webpack-bundle-page-data":
            return json.loads(script.text)
    raise ValueError("script#webpack-bundle-page-data not found")

def money(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    currency = value.get("currency")
    amount = value.get("amount")
    if currency is None and amount is None:
        return None
    return {"currency": currency, "amount": amount}

def load_bundles() -> list[dict[str, Any]]:
    data = json.loads(ALL_JSON.read_text(encoding="utf-8"))
    return [item for item in data.get("items", []) if item.get("url")][:MAX_BUNDLES]

def normalize_item(machine_name: str, raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not raw.get("human_name"):
        return None
    return {
        "title": raw.get("human_name"),
        "machine_name": raw.get("machine_name") or machine_name,
        "type": raw.get("item_content_type"),
        "min_price": money(raw.get("min_price|money") or raw.get("min_price")),
        "msrp_price": money(raw.get("msrp_price|money") or raw.get("msrp_price")),
        "platforms_and_oses": raw.get("platforms_and_oses") if isinstance(raw.get("platforms_and_oses"), dict) else {},
    }

def tier_sort_key(tier_key: str, pricing: dict[str, Any]) -> tuple[float, str]:
    price = money((pricing.get(tier_key) or {}).get("price|money"))
    amount = price.get("amount") if price else None
    return (float(amount) if amount is not None else float("inf"), tier_key)

def parse_bundle(source: dict[str, Any]) -> dict[str, Any]:
    page_data = extract_page_data(fetch_html(source["url"]))
    bundle = page_data.get("bundleData", {}) if isinstance(page_data, dict) else {}
    display = bundle.get("tier_display_data") or {}
    pricing = bundle.get("tier_pricing_data") or {}
    item_data = bundle.get("tier_item_data") or {}

    tier_keys = [key for key in list(bundle.get("tier_order") or display.keys()) if key in display]
    tier_keys = sorted(tier_keys, key=lambda key: tier_sort_key(key, pricing))

    tiers: list[dict[str, Any]] = []
    for key in tier_keys:
        tier_display = display.get(key) or {}
        tier_price_data = pricing.get(key) or {}
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item_key in tier_display.get("tier_item_machine_names") or []:
            if item_key in seen:
                continue
            seen.add(item_key)
            normalized = normalize_item(item_key, item_data.get(item_key))
            if normalized:
                items.append(normalized)
        tiers.append({
            "key": key,
            "header": tier_display.get("header"),
            "price": money(tier_price_data.get("price|money")),
            "average_purchase_price": money(tier_price_data.get("average_purchase_price|money")),
            "is_initial_tier": bool(tier_price_data.get("is_initial_tier")),
            "is_bta": bool(tier_price_data.get("is_bta")),
            "is_free": bool(tier_price_data.get("is_free")),
            "sold_out": bool(tier_display.get("sold_out")),
            "items": items,
        })

    return {
        "title": source.get("title"),
        "category": source.get("category"),
        "url": source.get("url"),
        "machine_name": bundle.get("machine_name") or source.get("machine_name"),
        "end_at": source.get("end_at"),
        "tiers": tiers,
    }

def main() -> int:
    output: dict[str, Any] = {"schema": "humble-watch-details-v1", "items": [], "errors": []}
    for source in load_bundles():
        try:
            output["items"].append(parse_bundle(source))
        except Exception as exc:
            output["errors"].append({
                "title": source.get("title"),
                "url": source.get("url"),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
    DETAILS_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if not output["errors"] else 1

if __name__ == "__main__":
    sys.exit(main())
