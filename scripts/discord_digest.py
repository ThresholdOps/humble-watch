#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DEFAULT_SITE_URL = "https://thresholdops.github.io/humble-watch/"
SITE_URL = os.environ.get("HUMBLE_WATCH_SITE_URL") or DEFAULT_SITE_URL
MAX_SECTION_ITEMS = 8
INTEREST_KEYWORDS = [
    "python",
    "cyberpunk",
    "rpg",
    "ttrpg",
    "unreal",
    "unity",
    "blender",
    "asset",
    "assets",
    "ai",
    "llm",
    "claude",
    "automation",
    "security",
    "cybersecurity",
    "world building",
    "worldbuilding",
]


def load_json(name: str) -> dict:
    path = DOCS / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def line_for(item: dict) -> str:
    title = item.get("title", "Untitled")
    category = item.get("category", "?")
    left = hours_text(item.get("hours_left"))
    return f"• **{title}** ({category}) — {left} left"


def section(title: str, items: list[dict]) -> str:
    if not items:
        return f"**{title}**\n_none_"
    shown = items[:MAX_SECTION_ITEMS]
    lines = [line_for(item) for item in shown]
    if len(items) > len(shown):
        lines.append(f"• …and {len(items) - len(shown)} more")
    return f"**{title}**\n" + "\n".join(lines)


def find_interesting(all_items: list[dict]) -> list[dict]:
    matches: list[dict] = []
    for item in all_items:
        haystack = " ".join([
            str(item.get("title", "")),
            str(item.get("description", "")),
            str(item.get("long_description", "")),
            str(item.get("category", "")),
        ]).lower()
        if any(keyword in haystack for keyword in INTEREST_KEYWORDS):
            matches.append(item)
    matches.sort(key=lambda x: float(x.get("hours_left", 999999) or 999999))
    return matches[:MAX_SECTION_ITEMS]


def build_message() -> str:
    all_data = load_json("all.json")
    urgent = load_json("urgent.json")
    all_items = all_data.get("items", [])
    generated_at = all_data.get("generated_at", "unknown")

    parts = [
        "📡 **Humble Watch Daily Digest**",
        f"Generated: `{generated_at}`",
        f"Dashboard: {SITE_URL}",
        "",
        section("Ending today", urgent.get("expires_today", [])),
        "",
        section("Ending tomorrow", urgent.get("expires_tomorrow", [])),
        "",
        section("Ending within 72h", urgent.get("expires_within_72h", [])),
        "",
        section("Interesting matches", find_interesting(all_items)),
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
