#!/usr/bin/env python3
"""Diagnostic Humble Bundle tier discovery helper.

This script does not try to parse tiers yet. It samples a few bundle URLs,
fetches their HTML, lists embedded script tags, and searches for likely tier
or product-data keywords. The output is intended for GitHub Actions logs and
as an artifact report.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPORT = DOCS / "tier-discovery-report.txt"
MAX_SAMPLE_PER_CATEGORY = 1
KEYWORDS = [
    "tier",
    "tiers",
    "amount",
    "price",
    "pay",
    "reward",
    "rewards",
    "product",
    "products",
    "human_name",
    "machine_name",
    "bundle",
    "contentChoiceOptions",
]


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


def load_sample_urls() -> list[dict[str, str]]:
    all_json = DOCS / "all.json"
    if not all_json.exists():
        raise FileNotFoundError(f"Missing {all_json}")

    data = json.loads(all_json.read_text(encoding="utf-8"))
    items = data.get("items", [])
    selected: list[dict[str, str]] = []
    seen_categories: dict[str, int] = {}

    for item in items:
        category = item.get("category") or "unknown"
        if seen_categories.get(category, 0) >= MAX_SAMPLE_PER_CATEGORY:
            continue
        url = item.get("url")
        if not url:
            continue
        selected.append({"category": category, "title": item.get("title", ""), "url": url})
        seen_categories[category] = seen_categories.get(category, 0) + 1

    return selected


def fetch_html(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; humble-watch-tier-discovery/0.1)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def discover_scripts(html: str) -> list[ScriptBlock]:
    parser = ScriptCollector()
    parser.feed(html)
    return parser.scripts


def summarize_script(idx: int, script: ScriptBlock) -> str:
    attrs = script.attrs
    ident = attrs.get("id") or ""
    src = attrs.get("src") or ""
    script_type = attrs.get("type") or ""
    text = script.text or ""
    matches = [kw for kw in KEYWORDS if re.search(re.escape(kw), text, flags=re.IGNORECASE)]
    return (
        f"  script[{idx}] id={ident!r} type={script_type!r} src={src!r} "
        f"inline_len={len(text)} keyword_matches={matches}\n"
    )


def keyword_contexts(html: str, keyword: str, limit: int = 3) -> list[str]:
    contexts: list[str] = []
    for match in re.finditer(re.escape(keyword), html, flags=re.IGNORECASE):
        start = max(0, match.start() - 140)
        end = min(len(html), match.end() + 140)
        snippet = re.sub(r"\s+", " ", html[start:end])
        contexts.append(snippet)
        if len(contexts) >= limit:
            break
    return contexts


def main() -> int:
    lines: list[str] = []
    lines.append("Humble Watch tier discovery report\n")
    lines.append("==================================\n\n")

    samples = load_sample_urls()
    lines.append(f"Sample count: {len(samples)}\n\n")

    for sample in samples:
        lines.append(f"# {sample['category']} — {sample['title']}\n")
        lines.append(f"URL: {sample['url']}\n")
        try:
            html = fetch_html(sample["url"])
            scripts = discover_scripts(html)
            lines.append(f"HTML length: {len(html)}\n")
            lines.append(f"Script count: {len(scripts)}\n")
            for idx, script in enumerate(scripts):
                summary = summarize_script(idx, script)
                if "keyword_matches=[]" not in summary or script.attrs.get("id"):
                    lines.append(summary)

            lines.append("Keyword contexts:\n")
            for keyword in KEYWORDS:
                contexts = keyword_contexts(html, keyword, limit=1)
                if contexts:
                    lines.append(f"  {keyword}: {contexts[0]}\n")
        except Exception as exc:  # diagnostics only
            lines.append(f"ERROR: {type(exc).__name__}: {exc}\n")
        lines.append("\n")

    REPORT.write_text("".join(lines), encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
