# Humble Watch

Personal Humble Bundle radar with RSS, JSON, live countdowns, and expandable tier views.

Live site: https://thresholdops.github.io/humble-watch/

This project is based on [`Feuerlord2/Humble-RSS-Site`](https://github.com/Feuerlord2/Humble-RSS-Site), originally created by Daniel Winter / Feuerlord2. It extends the original RSS generator with additional JSON outputs, bundle end dates, time-left calculations, tier parsing, and a table-based GitHub Pages frontend.

This project is not affiliated with Humble Bundle, Inc.

## Features

- RSS feeds for books, games, software, and all detected bundles.
- `all.json` with normalized bundle metadata.
- `urgent.json` with bundles grouped by expiry windows.
- `details.json` with parsed bundle tiers and tier items.
- Static GitHub Pages dashboard.
- Live countdown for bundles ending within 24 hours.
- Expandable tier chip UI showing new items per tier.
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

## Workflows

The repository includes GitHub Actions workflows for:

- Go test/build validation,
- manual feed generation,
- scheduled feed generation around 20:10 Europe/Warsaw,
- diagnostic tier discovery and parser workflows used during development.

The scheduled workflow uses UTC cron entries plus a Warsaw-local time gate to handle CEST/CET changes.

## Local usage

Requirements:

- Go 1.20+
- Python 3.12+ for details JSON generation

Build and generate feeds locally:

```bash
go build -o gohumble ./cmd/
cd docs
../gohumble
cd ..
python scripts/details_json_v1.py
```

Then open:

```text
docs/index.html
```

or inspect generated files:

```text
docs/all.json
docs/urgent.json
docs/details.json
docs/all.rss
```

## Attribution

This project is a derivative/fork of:

- Original project: [`Feuerlord2/Humble-RSS-Site`](https://github.com/Feuerlord2/Humble-RSS-Site)
- Original author: Daniel Winter / Feuerlord2
- Original inspiration noted upstream: `shimst3r/go-humble`

Additional changes in this fork are maintained under `ThresholdOps/humble-watch`.

## License

This project retains the upstream Apache License 2.0 license. See [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).
