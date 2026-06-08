#!/usr/bin/env python3
"""Discover Humble Bundle tier-to-item mapping structures.

This is intentionally diagnostic. It extracts compact summaries of the fields
that should connect tier prices to products: tier_order, tier_display_data,
tier_pricing_data, and tier_item_data.
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
OUT = DOCS / "tier-map-discovery.json"
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
            "User-Agent": "Mozilla/5.0 (compatible; humble-watch-tier-map-discovery/0.1)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_page_data(html: str) -> dict[str, Any]:
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


def compact(value: Any, depth: int = 0, max_depth: int = 4) -> Any:
    if depth >= max_depth:
        if isinstance(value, dict):
            return {"__type": "dict", "keys": sorted(value.keys())[:80]}
        if isinstance(value, list):
            return {"__type": "list", "len": len(value)}
        return value
    if isinstance(value, dict):
        return {k: compact(v, depth + 1, max_depth) for k, v in value.items()}
    if isinstance(value, list):
        return [compact(v, depth + 1, max_depth) for v in value[:80]]
    return value


def summarize_tier_items(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, Any] = {}
    for key, item in raw.items():
        if not isinstance(item, dict):
            continue
        result[key] = {
            "human_name": item.get("human_name"),
            "machine_name": item.get("machine_name"),
            "item_content_type": item.get("item_content_type"),
            "min_price": item.get("min_price|money") or item.get("min_price"),
            "msrp_price": item.get("msrp_price|money") or item.get("msrp_price"),
            "platforms_and_oses": item.get("platforms_and_oses"),
        }
    return result


def parse_bundle(item: dict[str, Any]) -> dict[str, Any]:
    data = extract_page_data(fetch_html(item["url"]))
    bundle = data.get("bundleData", {}) if isinstance(data, dict) else {}
    return {
        "source_title": item.get("title"),
        "source_category": item.get("category"),
        "url": item.get("url"),
        "bundle_machine_name": bundle.get("machine_name"),
        "tier_order": compact(bundle.get("tier_order"), max_depth=6),
        "tier_display_data": compact(bundle.get("tier_display_data"), max_depth=8),
        "tier_pricing_data": compact(bundle.get("tier_pricing_data"), max_depth=4),
        "tier_item_keys": sorted((bundle.get("tier_item_data") or {}).keys()),
        "tier_item_summary": summarize_tier_items(bundle.get("tier_item_data")),
    }


def main() -> int:
    output: dict[str, Any] = {
        "schema": "humble-watch-tier-map-discovery-v0.1",
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

    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if not output["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
