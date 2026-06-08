# Changelog

## 0.1.1 - Unreleased

### Fixed

- Stabilized the `ENDS` column width so localized date/time values stay on one line.
- Stabilized the `TIME LEFT` countdown rendering with a fixed-width monospace font.

## 0.1.0 - 2026-06-08

Initial usable Humble Watch release.

### Added

- RSS feeds for games, books, software, and all detected bundles.
- Combined `all.rss` feed.
- `all.json` with normalized bundle metadata.
- `urgent.json` with expiry-window groups.
- `details.json` with parsed bundle tiers and items.
- GitHub Pages static dashboard.
- Category filters, search, sortable columns, and summary counters.
- Live countdown for bundles ending within 24 hours.
- Expandable tier chip UI showing new items per tier.
- Manual and scheduled GitHub Actions generation.
- Diagnostic tier discovery and parser workflows used during development.

### Notes

- Tier prices are parsed from Humble Bundle page data and are currently represented as provided by Humble, typically in USD.
- The frontend displays new items per tier to avoid cumulative duplicate clutter.
