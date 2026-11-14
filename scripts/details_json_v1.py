#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
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
        prefix = "self.__next_f.push("
        content = script.text.strip()
        if not content.startswith(prefix) or not content.endswith(")"):
            continue
        try:
            chunk = json.loads(content[len(prefix):-1])
        except json.JSONDecodeError:
            continue
        if len(chunk) < 2 or not isinstance(chunk[1], str):
            continue
        marker = '{"bundlePage":'
        index = chunk[1].find(marker)
        if index >= 0:
            value, _ = json.JSONDecoder().raw_decode(chunk[1][index:])
            return value
    raise ValueError("bundle page data not found")

def money(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    currency = value.get("currency") or value.get("currencyCode")
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
    if "bundlePage" in page_data:
        return parse_next_bundle(source, page_data["bundlePage"])
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

def parse_next_bundle(source: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    raw_tiers = bundle.get("tiers") or []
    reference = re.compile(r"^\$[0-9a-f]+:0:props:children:props:bundlePage:tiers:(\d+):bundleItems:(\d+)$")

    def resolve_item(raw: Any, seen: set[tuple[int, int]] | None = None) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        match = reference.fullmatch(raw) if isinstance(raw, str) else None
        if not match:
            raise ValueError(f"unexpected bundle item reference: {raw!r}")
        position = (int(match.group(1)), int(match.group(2)))
        seen = seen or set()
        if position in seen:
            raise ValueError("cyclic bundle item reference")
        seen.add(position)
        return resolve_item(raw_tiers[position[0]]["bundleItems"][position[1]], seen)

    tiers: list[dict[str, Any]] = []
    for index, raw_tier in enumerate(sorted(raw_tiers, key=lambda tier: (tier.get("price") or {}).get("amount", float("inf")))):
        price = money(raw_tier.get("price"))
        items: list[dict[str, Any]] = []
        for raw_item in raw_tier.get("bundleItems") or []:
            raw_item = resolve_item(raw_item)
            if not raw_item.get("title"):
                continue
            platforms = raw_item.get("platforms") or []
            delivery = raw_item.get("deliveryMethods") or []
            metadata = {}
            if platforms:
                metadata["platforms"] = platforms
            if delivery:
                metadata["delivery_methods"] = delivery
            items.append({
                "title": raw_item["title"],
                "machine_name": raw_item.get("key") or raw_item.get("id"),
                "type": raw_item.get("bundleType"),
                "min_price": None,
                "msrp_price": None,
                "platforms_and_oses": metadata,
            })
        tiers.append({
            "key": raw_tier.get("sku") or raw_tier.get("id") or str(index + 1),
            "header": None,
            "price": price,
            "average_purchase_price": None,
            "is_initial_tier": index == 0,
            "is_bta": False,
            "is_free": bool(price and price.get("amount") == 0),
            "sold_out": False,
            "items": items,
        })
    if not tiers:
        raise ValueError("bundle page has no tiers")
    return {
        "title": source.get("title") or bundle.get("title"),
        "category": source.get("category") or bundle.get("bundleType"),
        "url": source.get("url"),
        "machine_name": source.get("machine_name"),
        "start_at": bundle.get("startDate"),
        "end_at": source.get("end_at"),
        "tiers": tiers,
    }

def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None

def build_details(sources: list[dict[str, Any]], previous: dict[str, Any], now: datetime,
                  refresh_after_hours: float = 168, refresh_all: bool = False) -> dict[str, Any]:
    cached = {item.get("url"): item for item in previous.get("items", []) if item.get("url")}
    output: dict[str, Any] = {"schema": "humble-watch-details-v1", "items": [], "errors": []}
    for source in sources:
        old = cached.get(source["url"])
        fetched_at = parse_timestamp(old.get("fetched_at")) if old else None
        age_hours = (now - fetched_at).total_seconds() / 3600 if fetched_at else float("inf")
        metadata_changed = old and (old.get("end_at") != source.get("end_at") or
                                    old.get("title") != source.get("title") or
                                    old.get("machine_name") != source.get("machine_name"))
        if old and not refresh_all and not metadata_changed and age_hours < refresh_after_hours:
            output["items"].append(old)
            continue
        try:
            parsed = parse_bundle(source)
            parsed["fetched_at"] = now.isoformat(timespec="seconds").replace("+00:00", "Z")
            output["items"].append(parsed)
        except Exception as exc:
            output["errors"].append({
                "title": source.get("title"),
                "url": source.get("url"),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
    return output

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate cached bundle tier details")
    parser.add_argument("--refresh-all", action="store_true", help="refetch every active bundle")
    parser.add_argument("--refresh-after-hours", type=float, default=168, help="maximum cache age (default: 168 hours)")
    args = parser.parse_args(argv)
    if args.refresh_after_hours < 0:
        parser.error("--refresh-after-hours must be nonnegative")
    previous = json.loads(DETAILS_JSON.read_text(encoding="utf-8")) if DETAILS_JSON.exists() else {"items": []}
    output = build_details(load_bundles(), previous, datetime.now(timezone.utc), args.refresh_after_hours, args.refresh_all)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    if output["errors"]:
        return 1
    DETAILS_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    sys.exit(main())
