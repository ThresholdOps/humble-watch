# Changelog

## 0.1.1 - 2026-06-08

### Added

- Discord daily digest after feed generation.
- `docs/seen.json` active-bundle snapshot for new-bundle tracking.
- `New bundles` section in the Discord digest.
- `config/interests.json` for configurable interest matching.
- Interest groups: `high`, `medium`, and `ignore`.
- Local setup documentation in `docs/setup-local.md`.

### Changed

- Discord digest uses compact emoji sections and bullet lines.
- Dashboard URL in Discord digest is wrapped to reduce unwanted preview clutter.
- Removed the redundant `Ending within 72h` section from the Discord digest.
- `Interesting matches` no longer displays matched keywords in Discord to preserve title space.

### Fixed

- Stabilized the `ENDS` column width so localized date/time values stay on one line.
- Stabilized the `TIME LEFT` column width.
- Live countdown uses a fixed-width monospace font so timer digits do not visually jump.

### Notes

- `seen.json` is a current active-bundle snapshot, not a historical archive.
- First run without `seen.json` initializes tracking without reporting every active bundle as new.

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
