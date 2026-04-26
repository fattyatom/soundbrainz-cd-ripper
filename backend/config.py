import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".soundbrainz"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "output_dir": str(Path.home() / "Music"),
    "folder_pattern": "{artist}/{album}/{number:02d} - {title}.flac",
    "folder_pattern_multi_disc": "{artist}/{album}/CD{disc}/{number:02d} - {title}.flac",
    "preferred_languages": ["en"],
    "preferred_country": "",
    "preferred_genre": "",
    "default_drive": "",
    "rip_speed": "balanced",  # Options: accurate, balanced, fast
}


def load_config() -> dict:
    """Load config from disk, merged with defaults."""
    config = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
        config.update(saved)
    return config


def save_config(data: dict) -> None:
    """Save config to disk. Creates config dir if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def update_config(updates: dict) -> dict:
    """Merge updates into existing config and save."""
    config = load_config()
    config.update(updates)
    save_config(config)
    return config