# SoundBrainz CD Ripper

A web-based CD ripper that extracts audio CDs to lossless FLAC with MusicBrainz metadata and cover art.

## Features

- Detect USB and SATA CD/DVD drives
- Bit-perfect CD ripping via cdparanoia
- MusicBrainz disc lookup with cover art from Cover Art Archive
- Lossless FLAC transcoding via ffmpeg
- Automatic library folder organization with configurable naming patterns
- User preferences for language, country, and genre prioritization

## System Dependencies

Install these before running:

```bash
# macOS
brew install libcdio-paranoia ffmpeg libdiscid

# Ubuntu/Debian
sudo apt install cdparanoia ffmpeg libdiscid-dev
```

> **Note:** On macOS, `cdparanoia` is not available via Homebrew. The app uses `cd-paranoia` from `libcdio-paranoia` instead (same functionality, actively maintained). The app auto-detects which one is installed.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
source venv/bin/activate
python run.py
```

Open http://localhost:5000 in your browser.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/drives` | List detected CD drives |
| POST | `/api/drives/eject` | Eject disc from drive |
| GET | `/api/lookup?device=...` | Look up disc on MusicBrainz |
| POST | `/api/rip` | Start rip job |
| GET | `/api/rip/status` | Get rip progress |
| GET | `/api/settings` | Get settings |
| POST | `/api/settings` | Update settings |
| GET | `/api/library/detect-structure?dir=...` | Detect library folder pattern |
| GET | `/api/health` | Check system dependencies |

## License

Apache License 2.0
