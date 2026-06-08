# Humble Watch

Personal Humble Bundle radar with RSS, JSON, live countdowns, expandable tier views, and Discord digests.

Live site: https://thresholdops.github.io/humble-watch/

This project is based on [`Feuerlord2/Humble-RSS-Site`](https://github.com/Feuerlord2/Humble-RSS-Site), originally created by Daniel Winter / Feuerlord2. It extends the original RSS generator with additional JSON outputs, bundle end dates, time-left calculations, tier parsing, Discord notifications, and a table-based GitHub Pages frontend.

This project is not affiliated with Humble Bundle, Inc.

## Features

- RSS feeds for books, games, software, and all detected bundles.
- `all.json` with normalized bundle metadata.
- `urgent.json` with bundles grouped by expiry windows.
- `details.json` with parsed bundle tiers and tier items.
- `seen.json` active-bundle snapshot for new-bundle tracking.
- Static GitHub Pages dashboard.
- Live countdown for bundles ending within 24 hours.
- Expandable tier chip UI showing new items per tier.
- Configurable interest matching through `config/interests.json`.
- Compact Discord daily digest with new bundles, ending-today, ending-tomorrow, and interesting matches.
- Manual and scheduled GitHub Actions generation.

## Generated outputs

The generated files are published from `docs/`:

- `docs/books.rss` — book bundle RSS feed
- `docs/games.rss` — game bundle RSS feed
- `docs/software.rss` — software bundle RSS feed
- `docs/all.rss` — combined RSS feed
- `docs/all.json` — normalized machine-readable list of all detected bundles
- `docs/urgent.json` — bundles expiring within short time windows
- `docs/details.json` — parsed tier and item details for bundle pages
- `docs/seen.json` — current active-bundle snapshot used for detecting new bundles

`all.json` includes fields such as:

- `category`
- `title`
- `url`
- `description`
- `start_at`
- `end_at`
- `days_left`
- `hours_left`
- `machine_name`
- `bundles_sold`
- `tile_stamp`

`details.json` includes bundle tier data such as:

- tier key and header
- tier price
- average purchase price when available
- item titles
- item machine names
- item type
- platform / OS metadata when available

`seen.json` is not a history archive. It is rewritten after each successful digest run so it contains only currently active bundles.

## Static dashboard

`docs/index.html` provides a static table frontend over `all.json` and `details.json`.

It includes:

- category filters,
- urgent `<72h` filter,
- search over bundle and tier item names,
- sortable table columns,
- summary counters,
- live countdown display,
- expandable tier chip panels,
- links to generated RSS and JSON files.

When GitHub Pages is configured for `main` + `/docs`, the dashboard is served as a static site.

## Discord digest

The main generation workflow can send a Discord digest when `DISCORD_WEBHOOK_URL` is configured as a repository secret.

Optional repository variable:

- `HUMBLE_WATCH_SITE_URL` — dashboard URL used in the digest. Falls back to the GitHub Pages URL.

The digest currently includes:

- new bundles detected since the previous `seen.json` snapshot,
- bundles ending today,
- bundles ending tomorrow,
- interesting matches from `config/interests.json`.

## Workflows

The repository includes GitHub Actions workflows for:

- Go test/build validation,
- manual feed generation,
- scheduled feed generation around 20:10 Europe/Warsaw,
- Discord digest delivery after generation,
- diagnostic tier discovery and parser workflows used during development.

The scheduled workflow uses UTC cron entries plus a Warsaw-local time gate to handle CEST/CET changes.

## Local setup

See [`docs/setup-local.md`](./docs/setup-local.md) for local installation, generation, dashboard preview, and optional Discord digest testing.

Quick local preview:

```bash
go build -o gohumble ./cmd/
cd docs
../gohumble
cd ..
python scripts/details_json_v1.py
python -m http.server 8000 -d docs
```

Then open:

```text
http://localhost:8000
```

## Attribution

This project is a derivative/fork of:

- Original project: [`Feuerlord2/Humble-RSS-Site`](https://github.com/Feuerlord2/Humble-RSS-Site)
- Original author: Daniel Winter / Feuerlord2
- Original inspiration noted upstream: `shimst3r/go-humble`

Additional changes in this fork are maintained under `ThresholdOps/humble-watch`.

## License

This project retains the upstream Apache License 2.0 license. See [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).
