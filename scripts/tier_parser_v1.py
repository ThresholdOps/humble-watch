#!/usr/bin/env python3
"""Parse first-pass Humble Bundle tier data into docs/details.json.

This is a v1 parser. It extracts the bundle page JSON from
script#webpack-bundle-page-data and records the most important tier-related
objects without assuming the final UI schema yet.
"""

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
MAX_SAMPLE_PER_CATEGORY = 2


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
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; humble-watch-tier-parser/0.1)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_bundle_page_data(html: str) -> dict[str, Any]:
    parser = ScriptCollector()
    parser.feed(html)
    for script in parser.scripts:
        if script.attrs.get("id") == "webpack-bundle-page-data":
            return json.loads(script.text)
    raise ValueError("script#webpack-bundle-page-data not found")


def load_samples() -> list[dict[str, Any]]:
    data = json.loads(ALL_JSON.read_text(encoding="utf-8"))
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for item in data.get("items", []):
        category = item.get("category") or "unknown"
        if counts.get(category, 0) >= MAX_SAMPLE_PER_CATEGORY:
            continue
        if not item.get("url"):
            continue
        selected.append(item)
        counts[category] = counts.get(category, 0) + 1
    return selected


def money(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return {
            "currency": value.get("currency"),
            "amount": value.get("amount"),
        }
    return None


def summarize_tier_pricing(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    tiers: list[dict[str, Any]] = []
    for key, value in raw.items():
        if not isinstance(value, dict):
            tiers.append({"key": key, "raw_type": type(value).__name__})
            continue
        tiers.append({
            "key": key,
            "price": money(value.get("price|money")),
            "display_price": value.get("display_price"),
            "human_name": value.get("human_name"),
            "machine_name": value.get("machine_name"),
            "fields": sorted(value.keys()),
        })
    return tiers


def summarize_content_events(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    events: list[dict[str, Any]] = []
    for event in raw:
        if not isinstance(event, dict):
            continue
        events.append({
            "identifier": event.get("identifier"),
            "type": event.get("type"),
            "price": event.get("price"),
            "start": event.get("start"),
            "has_subproducts": event.get("has_subproducts"),
            "section_identifiers": event.get("section_identifiers"),
            "fields": sorted(event.keys()),
        })
    return events


def find_likely_product_containers(value: Any, path: str = "", limit: int = 25) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(node: Any, current_path: str) -> None:
        if len(found) >= limit:
            return
        if isinstance(node, dict):
            keys = set(node.keys())
            if {"human_name", "machine_name"}.issubset(keys):
                found.append({
                    "path": current_path,
                    "human_name": node.get("human_name"),
                    "machine_name": node.get("machine_name"),
                    "keys": sorted(node.keys())[:40],
                })
            for key, child in node.items():
                walk(child, f"{current_path}.{key}" if current_path else key)
        elif isinstance(node, list):
            for idx, child in enumerate(node[:50]):
                walk(child, f"{current_path}[{idx}]")

    walk(value, path)
    return found


def parse_bundle(item: dict[str, Any]) -> dict[str, Any]:
    html = fetch_html(item["url"])
    page_data = extract_bundle_page_data(html)
    bundle_data = page_data.get("bundleData", {}) if isinstance(page_data, dict) else {}

    return {
        "source_title": item.get("title"),
        "source_category": item.get("category"),
        "url": item.get("url"),
        "bundle": {
            "human_name": bundle_data.get("human_name"),
            "machine_name": bundle_data.get("machine_name"),
            "end_at": bundle_data.get("end_time|datetime"),
            "msrp": money(bundle_data.get("msrp|money")),
            "tpkd_cutoff_price": money(bundle_data.get("tpkd_cutoff_price|money")),
        },
        "tier_pricing_data": summarize_tier_pricing(bundle_data.get("tier_pricing_data")),
        "cached_content_events": summarize_content_events(bundle_data.get("cached_content_events")),
        "likely_product_containers": find_likely_product_containers(bundle_data),
        "bundle_data_top_level_fields": sorted(bundle_data.keys()) if isinstance(bundle_data, dict) else [],
    }


def main() -> int:
    output: dict[str, Any] = {
        "schema": "humble-watch-details-v0.1-diagnostic",
        "sample_limit_per_category": MAX_SAMPLE_PER_CATEGORY,
        "items": [],
        "errors": [],
    }

    for item in load_samples():
        try:
            output["items"].append(parse_bundle(item))
        except Exception as exc:
            output["errors"].append({
                "title": item.get("title"),
                "url": item.get("url"),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    DETAILS_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if not output["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
