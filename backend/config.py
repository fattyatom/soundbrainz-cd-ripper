import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".soundbrainz"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "output_dir": str(Path.home() / "Music"),
    "folder_pattern": "{album_artist}/{album}/{number:02d} - {title}.{ext}",
    "folder_pattern_multi_disc": "{album_artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}",
    "preferred_languages": ["en"],
    "preferred_country": "",
    "preferred_genre": "",
    "default_drive": "",
    # New audio quality settings (replaces rip_speed)
    "audio_format": "aiff",  # Options: "flac", "aiff", "wav"
    "flac_compression_level": 5,  # 0-12, only used for FLAC format (default 5 for better error handling)
    "quality_preset": "audiophile",  # Options: "audiophile", "portable", "archive", "custom"
    # Quality-based cdparanoia settings (controlled by quality_preset)
    "rip_speed": "1",  # "1" (audiophile), "8" (archive), "max" (portable)
    "cdparanoia_overlap": "0",  # Can be increased for damaged discs
    "cdparanoia_abort_on_skip": True,  # Fail fast on uncorrectable errors
    "cdparanoia_never_skip": True,  # Maximum error recovery
    "enable_checksums": True,  # Always enable SHA-256 checksums
    "auto_eject": True,  # Automatically eject disc after successful rip
}


# Quality preset definitions - these override individual settings when a preset is selected
QUALITY_PRESETS = {
    "audiophile": {
        "audio_format": "aiff",  # Uncompressed for maximum quality
        "rip_speed": "1",
        "cdparanoia_abort_on_skip": True,
        "cdparanoia_never_skip": True,
        "cdparanoia_verbose": True,
        "enable_checksums": True,
        "flac_compression_level": 5,  # Not used for AIFF, but good default if format changes
    },
    "portable": {
        "audio_format": "flac",  # Compressed for portability
        "rip_speed": "max",
        "cdparanoia_abort_on_skip": False,
        "cdparanoia_never_skip": False,
        "cdparanoia_verbose": False,
        "enable_checksums": True,
        "flac_compression_level": 5,  # Balanced compression
    },
    "archive": {
        "audio_format": "flac",  # Compressed for storage
        "rip_speed": "8",
        "cdparanoia_abort_on_skip": True,
        "cdparanoia_never_skip": True,
        "cdparanoia_verbose": True,
        "enable_checksums": True,
        "flac_compression_level": 8,  # Higher compression for storage efficiency
    },
}


def migrate_config(config: dict) -> dict:
    """Migrate existing configuration to new format.

    Handles:
    - Removing old rip_speed setting
    - Adding new audio quality settings with sensible defaults
    - Converting old folder patterns to use dynamic extensions
    - Migrating {artist} to {album_artist} in folder patterns
    """
    # Remove old rip_speed setting
    if "rip_speed" in config:
        del config["rip_speed"]

    # Add new audio quality settings with sensible defaults
    if "audio_format" not in config:
        config["audio_format"] = "aiff"  # Default to uncompressed AIFF

    if "flac_compression_level" not in config:
        config["flac_compression_level"] = 5  # Default to balanced compression (better than 0)

    if "quality_preset" not in config:
        config["quality_preset"] = "audiophile"

    # Migrate folder patterns from hardcoded .flac to dynamic {ext}
    if config.get("folder_pattern", "").endswith(".flac"):
        config["folder_pattern"] = config["folder_pattern"][:-5] + ".{ext}"
    if config.get("folder_pattern_multi_disc", "").endswith(".flac"):
        config["folder_pattern_multi_disc"] = config["folder_pattern_multi_disc"][:-5] + ".{ext}"

    # Migrate folder patterns from {artist} to {album_artist}
    def migrate_artist_to_album_artist(pattern: str) -> str:
        """Migrate {artist} to {album_artist} in folder patterns.

        Rules:
        1. Exact default patterns → replace with new defaults
        2. Simple patterns starting with {artist}/ → substitute
        3. Complex/custom patterns → leave unchanged
        """
        old_single = "{artist}/{album}/{number:02d} - {title}.{ext}"
        new_single = "{album_artist}/{album}/{number:02d} - {title}.{ext}"
        old_multi = "{artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}"
        new_multi = "{album_artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}"

        # Exact matches to old defaults
        if pattern == old_single:
            return new_single
        if pattern == old_multi:
            return new_multi

        # Simple substitution for patterns starting with {artist}/
        # Only migrate if {artist} appears once at the start (simple customization)
        if pattern.startswith("{artist}/") and pattern.count("{artist}") == 1:
            return pattern.replace("{artist}/", "{album_artist}/", 1)

        # Complex or custom pattern - leave unchanged
        return pattern

    config["folder_pattern"] = migrate_artist_to_album_artist(config.get("folder_pattern", DEFAULTS["folder_pattern"]))
    config["folder_pattern_multi_disc"] = migrate_artist_to_album_artist(config.get("folder_pattern_multi_disc", DEFAULTS["folder_pattern_multi_disc"]))

    return config


def get_effective_config(config: dict) -> dict:
    """Merge preset settings with user config.

    When a quality_preset is selected, preset values override individual settings
    unless the user has explicitly set those values (for custom preset).

    Args:
        config: User configuration dictionary

    Returns:
        Configuration dictionary with preset values applied
    """
    preset = config.get("quality_preset", "audiophile")

    # Only apply preset if it's not "custom"
    if preset != "custom" and preset in QUALITY_PRESETS:
        preset_settings = QUALITY_PRESETS[preset]

        # Create a copy of config to avoid modifying the original
        effective = dict(config)

        # Apply preset settings for keys that exist in the preset
        for key, value in preset_settings.items():
            # Don't override if user explicitly set this value (not from DEFAULTS)
            # We detect this by checking if the value differs from DEFAULTS
            if key not in DEFAULTS or DEFAULTS[key] == config.get(key):
                effective[key] = value

        return effective

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