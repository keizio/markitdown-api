# markitdown-api

Stateless Flask API that converts a document URL to Markdown using Microsoft [`markitdown`](https://github.com/microsoft/markitdown).

Send it a URL, get back `text/markdown`.

## Features

- `POST /convert` — download a document from URL and return Markdown
- `GET /health` — health check for Docker / Coolify / load balancers
- API-key auth via `X-API-Key` header
- Extension + MIME-type validation (`text/*` allowed)
- Download size cap and timeout with clean error codes
- Docker-ready, GHCR-published, Coolify-ready

## Quickstart

### Docker Compose (local)

```bash
cp .env.example .env
# edit .env and set API_KEY
docker compose up -d --build
curl http://localhost:8000/health
# {"status":"ok"}
```

### Coolify

1. New Resource → Docker Compose → paste contents of `docker-compose.coolify.yml`
2. Set `API_KEY` (required) in Environment Variables
3. Deploy — Coolify handles HTTPS + routing, no host port mapping needed

Image: `ghcr.io/keizio/markitdown-api:latest`

### Local dev (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
API_KEY=change-me python app.py
# or: gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 120 app:app
```

## Configuration

| Var | Required | Default | Description |
| --- | --- | --- | --- |
| `API_KEY` | Yes | — | Compared against `X-API-Key` header |
| `PORT` | No | `8000` | Flask / gunicorn listen port |
| `MAX_DOWNLOAD_BYTES` | No | `52428800` (50 MB) | Requests over this return `413 file_too_large` |
| `DOWNLOAD_TIMEOUT` | No | `30` | Upstream download timeout in seconds |

See [`.env.example`](.env.example).

## API Reference

### `GET /health`

No auth required.

```bash
curl http://localhost:8000/health
```

```json
{ "status": "ok" }
```

### `POST /convert`

Auth: `X-API-Key: <API_KEY>` header required.
Body: JSON `{ "url": "https://..." }` (only `http`/`https` allowed).
Success: `200` with `Content-Type: text/markdown; charset=utf-8`, body is Markdown.

```bash
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{"url":"https://example.com/document.pdf"}'
```

### Errors

All errors are JSON `{ "error": "<code>", ... }`:

| Status | `error` | When |
| --- | --- | --- |
| 401 | `unauthorized` | Missing / wrong `X-API-Key` |
| 500 | `server_api_key_not_configured` | `API_KEY` not set server-side |
| 400 | `url_required` | Missing / non-string `url` |
| 400 | `invalid_url_scheme` | Not `http`/`https` |
| 415 | `unsupported_document_type` | Extension + MIME not in allowlist (returns `extension`, `mime`) |
| 413 | `file_too_large` | Exceeds `MAX_DOWNLOAD_BYTES` |
| 502 | `download_failed` | Upstream fetch failed (returns `detail`) |
| 422 | `conversion_failed` | `markitdown` failed (returns `detail`) |

## Supported types

By extension (or MIME fallback):

`pdf, doc, docx, ppt, pptx, xls, xlsx, csv, tsv, json, xml, html, htm, txt, md, rst, rtf, epub, odt, ods, odp, msg`

Any `text/*` MIME type is also accepted. See `DOCUMENT_EXTENSIONS` / `DOCUMENT_MIME_TYPES` in [`app.py`](app.py).

## Deployment

- `Dockerfile` — `python:3.12-slim`, gunicorn with 2 workers, 120s timeout, `/health` healthcheck
- `docker-compose.yml` — local deploy, maps `${PORT:-8000}:8000`, uses `.env`
- `docker-compose.coolify.yml` — Coolify deploy, `expose: 8000` only, requires `API_KEY`
- CI: [`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml) builds and pushes to GHCR on `main` (`latest` + `branch-sha`) and tags (`v*`)

## Notes / Limits

- Downloads are buffered in memory up to `MAX_DOWNLOAD_BYTES`, then converted via `convert_stream`
- Only scheme validation is done on `url` — if you expose this publicly, consider SSRF protections (private-IP blocking) in front of it
- `/health` is unauthenticated by design
