# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Run (dev server on http://localhost:5000)
source venv/bin/activate && python run.py

# Run all tests
source venv/bin/activate && pytest

# Run a single test
pytest tests/test_drive_service.py::TestDetectDrivesMacOS::test_detects_usb_drive_with_disc
```

System dependencies (not in requirements.txt): `cdparanoia`/`cd-paranoia`, `ffmpeg`, `libdiscid`. On macOS: `brew install libcdio-paranoia ffmpeg libdiscid`. On Linux: `apt install cdparanoia ffmpeg libdiscid-dev`.

## Architecture

**Flask backend + vanilla JS frontend (no build step).**

`run.py` → `backend/__init__.py:create_app()` registers four blueprints and serves `frontend/` as static files.

### Backend

Routes in `backend/routes/` are thin — they delegate to services in `backend/services/`:

| Service | Responsibility |
| --- | --- |
| `drive_service` | Detect optical drives (macOS via `system_profiler`/`diskutil`, Linux via `/sys/block`); eject |
| `musicbrainz_service` | Read disc ID via `libdiscid`; look up release on MusicBrainz (exact disc ID, TOC fallback); normalize release data |
| `coverart_service` | Download cover art from Cover Art Archive by release MBID |
| `ripper_service` | Orchestrate the full rip pipeline in a background thread; expose `rip_state` dict for polling |
| `transcoder_service` | WAV → FLAC via ffmpeg, embedding per-track metadata and cover art |
| `library_service` | Resolve final file paths from a configurable pattern string and move files into the library |

**Rip pipeline** (`ripper_service._rip_worker`):
1. Rip disc to per-track WAV files in a temp dir (cdparanoia)
2. Download cover art to temp dir
3. Transcode WAVs → FLACs in a second temp dir (ffmpeg)
4. Move FLACs into the library folder using the configured pattern; clean up both temp dirs

Progress is tracked in a module-level `rip_state` dict (protected by `_rip_lock`). Only one rip can run at a time. The frontend polls `/api/rip/status`.

**cdparanoia binary**: `_find_cdparanoia()` in `ripper_service` prefers `cd-paranoia` (macOS) over `cdparanoia` (Linux). The same logic applies in the health check in `backend/__init__.py`.

**Config** is stored at `~/.soundbrainz/config.json`. `backend/config.py` handles load/save/update with defaults. The `folder_pattern` key uses Python format strings: `{artist}/{album}/{number:02d} - {title}.flac`.

### Frontend

Plain JS modules in `frontend/js/` loaded via `<script>` tags (no bundler). Each file is a singleton object:
- `app.js` — view switching, toast notifications
- `api.js` — all `fetch()` calls to the backend
- `drives.js` — drive list and rip initiation
- `metadata.js` — release selection UI after MusicBrainz lookup
- `rip.js` — rip progress polling
- `settings.js` — settings form
