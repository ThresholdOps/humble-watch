#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CONFIG = ROOT / "config"
INTERESTS_JSON = CONFIG / "interests.json"
SEEN_JSON = DOCS / "seen.json"
DEFAULT_SITE_URL = "https://thresholdops.github.io/humble-watch/"
SITE_URL = os.environ.get("HUMBLE_WATCH_SITE_URL") or DEFAULT_SITE_URL
MAX_SECTION_ITEMS = 5
TITLE_WIDTH = 82
DEFAULT_INTERESTS = {
    "high": ["python", "unreal", "unity", "blender", "world of darkness"],
    "medium": ["rpg", "ttrpg", "asset", "assets", "automation", "claude", "llm", "ai", "world building", "worldbuilding"],
    "ignore": ["manga", "embroidery"],
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(name: str) -> dict:
    path = DOCS / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_interests() -> dict:
    if not INTERESTS_JSON.exists():
        return DEFAULT_INTERESTS
    try:
        data = json.loads(INTERESTS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return DEFAULT_INTERESTS
    return {
        "high": data.get("high", []),
        "medium": data.get("medium", []),
        "ignore": data.get("ignore", []),
    }


def bundle_key(item: dict) -> str:
    return item.get("machine_name") or item.get("url") or item.get("title", "")


def hours_text(value) -> str:
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if hours <= 0:
        return "ended"
    if hours < 24:
        whole = int(hours)
        minutes = int((hours - whole) * 60)
        return f"{whole}h {minutes}m"
    days = int(hours // 24)
    rest = int(hours % 24)
    return f"{days}d {rest}h"


def truncate(value: str, width: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= width:
        return value
    return value[: max(0, width - 1)] + "…"


def compact_line(item: dict) -> str:
    category = item.get("category", "?")
    left = hours_text(item.get("hours_left"))
    title = truncate(item.get("title", "Untitled"), TITLE_WIDTH)
    return f"• {category} · {left} · {title}"


def section(title: str, items: list[dict], icon: str) -> str:
    header = f"{icon} **{title}**"
    if not items:
        return f"{header}\nnone"
    shown = items[:MAX_SECTION_ITEMS]
    lines = [compact_line(item) for item in shown]
    if len(items) > len(shown):
        lines.append(f"• …and {len(items) - len(shown)} more")
    return header + "\n" + "\n".join(lines)


def load_seen() -> dict:
    if not SEEN_JSON.exists():
        return {"items": [], "initialized": False}
    try:
        data = json.loads(SEEN_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"items": [], "initialized": False}
    data["initialized"] = True
    return data


def current_seen_snapshot(all_items: list[dict], generated_at: str) -> dict:
    return {
        "generated_at": generated_at,
        "updated_at": now_utc(),
        "items": [
            {
                "key": bundle_key(item),
                "url": item.get("url"),
                "machine_name": item.get("machine_name"),
                "title": item.get("title"),
                "category": item.get("category"),
                "end_at": item.get("end_at"),
            }
            for item in all_items
            if bundle_key(item)
        ],
    }


def find_new_bundles(all_items: list[dict], seen: dict) -> list[dict]:
    if not seen.get("initialized"):
        return []
    seen_keys = {item.get("key") or item.get("machine_name") or item.get("url") for item in seen.get("items", [])}
    seen_keys.discard(None)
    return [item for item in all_items if bundle_key(item) and bundle_key(item) not in seen_keys]


def write_seen(all_items: list[dict], generated_at: str) -> None:
    snapshot = current_seen_snapshot(all_items, generated_at)
    SEEN_JSON.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def item_haystack(item: dict) -> str:
    return " ".join([
        str(item.get("title", "")),
        str(item.get("description", "")),
        str(item.get("long_description", "")),
        str(item.get("category", "")),
    ]).lower()


def matched_keywords(haystack: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword.lower() in haystack]


def find_interesting(all_items: list[dict]) -> list[dict]:
    interests = load_interests()
    high = interests.get("high", [])
    medium = interests.get("medium", [])
    ignore = interests.get("ignore", [])
    matches: list[dict] = []
    for item in all_items:
        haystack = item_haystack(item)
        if matched_keywords(haystack, ignore):
            continue
        high_matches = matched_keywords(haystack, high)
        medium_matches = matched_keywords(haystack, medium)
        if not high_matches and not medium_matches:
            continue
        enriched = dict(item)
        enriched["interest_rank"] = 0 if high_matches else 1
        matches.append(enriched)
    matches.sort(key=lambda x: (x.get("interest_rank", 9), float(x.get("hours_left", 999999) or 999999)))
    return matches[:MAX_SECTION_ITEMS]


def build_message() -> str:
    all_data = load_json("all.json")
    urgent = load_json("urgent.json")
    seen = load_seen()
    all_items = all_data.get("items", [])
    generated_at = all_data.get("generated_at", "unknown")
    new_bundles = find_new_bundles(all_items, seen)
    write_seen(all_items, generated_at)

    parts = [
        "📡 **Humble Watch Daily Digest**",
        f"Generated: `{generated_at}`",
        f"Dashboard: <{SITE_URL}>",
        "",
        section("New bundles", new_bundles, "🆕"),
        "",
        section("Ending today", urgent.get("expires_today", []), "⏳"),
        "",
        section("Ending tomorrow", urgent.get("expires_tomorrow", []), "🌅"),
        "",
        section("Interesting matches", find_interesting(all_items), "🎯"),
    ]
    return "\n".join(parts)


def send_discord(content: str) -> None:
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("DISCORD_WEBHOOK_URL is not set; skipping Discord digest.")
        return
    payload = json.dumps({"content": content[:1900]}).encode("utf-8")
    req = request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "humble-watch-discord-digest/0.1"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        print(f"Discord response: {response.status}")


def main() -> int:
    message = build_message()
    print(message)
    send_discord(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
