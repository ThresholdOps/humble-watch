# Local setup

This guide explains how to run Humble Watch locally for development or personal use.

## Requirements

- Git
- Go 1.20+
- Python 3.12+

No external Python package installation is required for the current scripts.

## Clone the repository

```bash
git clone https://github.com/ThresholdOps/humble-watch.git
cd humble-watch
```

## Generate RSS and base JSON files

Build the Go generator and run it from the `docs/` directory:

```bash
go build -o gohumble ./cmd/
cd docs
../gohumble
cd ..
```

This should generate or update:

```text
docs/books.rss
docs/games.rss
docs/software.rss
docs/all.rss
docs/all.json
docs/urgent.json
```

## Generate bundle tier details

Run the Python details generator:

```bash
python scripts/details_json_v1.py
```

This should generate:

```text
docs/details.json
```

## Preview the dashboard locally

Use a local HTTP server. Do not rely on opening `docs/index.html` directly from disk, because browser `file://` mode may block `fetch()` calls for JSON files.

```bash
python -m http.server 8000 -d docs
```

Open:

```text
http://localhost:8000
```

## Configure interest matching

Edit:

```text
config/interests.json
```

The file supports three groups:

```json
{
  "high": ["python", "unreal", "unity"],
  "medium": ["rpg", "ttrpg", "automation"],
  "ignore": ["manga", "embroidery"]
}
```

`ignore` excludes matching bundles from the Discord `Interesting matches` section.

## Test Discord digest locally

Set environment variables and run the digest script:

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export HUMBLE_WATCH_SITE_URL="http://localhost:8000/"
python scripts/discord_digest.py
```

On Windows PowerShell:

```powershell
$env:DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
$env:HUMBLE_WATCH_SITE_URL="http://localhost:8000/"
python scripts/discord_digest.py
```

If `DISCORD_WEBHOOK_URL` is missing, the script prints the digest and skips sending to Discord.

## New-bundle tracking

The Discord digest uses:

```text
docs/seen.json
```

`seen.json` is a snapshot of currently active bundles from the previous successful digest run.

Behavior:

- If `seen.json` does not exist, the first run initializes it and reports no new bundles.
- Later runs compare `all.json` with `seen.json` and report newly detected active bundles.
- After each run, `seen.json` is rewritten from the current active bundle list.
- Expired or removed bundles disappear from `seen.json` automatically.

## Typical local refresh sequence

```bash
go build -o gohumble ./cmd/
cd docs
../gohumble
cd ..
python scripts/details_json_v1.py
python scripts/discord_digest.py
python -m http.server 8000 -d docs
```
