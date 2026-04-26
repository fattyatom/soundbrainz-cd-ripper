import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".soundbrainz"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "output_dir": str(Path.home() / "Music"),
    "folder_pattern": "{artist}/{album}/{number:02d} - {title}.{ext}",
    "folder_pattern_multi_disc": "{artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}",
    "preferred_languages": ["en"],
    "preferred_country": "",
    "preferred_genre": "",
    "default_drive": "",
    # New audio quality settings (replaces rip_speed)
    "audio_format": "aiff",  # Options: "flac", "aiff", "wav"
    "flac_compression_level": 0,  # 0-12, only used for FLAC format
    "quality_preset": "audiophile",  # Options: "audiophile", "portable", "archive", "custom"
}


def migrate_config(config: dict) -> dict:
    """Migrate existing configuration to new format.

    Handles:
    - Removing old rip_speed setting
    - Adding new audio quality settings with sensible defaults
    - Converting old folder patterns to use dynamic extensions
    """
    # Remove old rip_speed setting
    if "rip_speed" in config:
        del config["rip_speed"]

    # Add new audio quality settings with sensible defaults
    if "audio_format" not in config:
        config["audio_format"] = "aiff"  # Default to uncompressed AIFF

    if "flac_compression_level" not in config:
        config["flac_compression_level"] = 0  # Default to no compression

    if "quality_preset" not in config:
        config["quality_preset"] = "audiophile"

    # Migrate folder patterns from hardcoded .flac to dynamic {ext}
    if config.get("folder_pattern", "").endswith(".flac"):
        config["folder_pattern"] = config["folder_pattern"][:-5] + ".{ext}"
    if config.get("folder_pattern_multi_disc", "").endswith(".flac"):
        config["folder_pattern_multi_disc"] = config["folder_pattern_multi_disc"][:-5] + ".{ext}"

    return config


def load_config() -> dict:
    """Load config from disk, merged with defaults and migrated to new format."""
    config = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
        config.update(saved)

    # Migrate to new format
    config = migrate_config(config)

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