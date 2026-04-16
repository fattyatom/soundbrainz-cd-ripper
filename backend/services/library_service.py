import logging
import os
import re
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

# Common audio file extensions
AUDIO_EXTENSIONS = {".flac", ".wav", ".mp3", ".m4a", ".ogg", ".opus", ".wma", ".aiff"}


def detect_structure(root_dir: str) -> str | None:
    """Analyze an existing music library folder to infer the naming pattern.

    Walks the directory up to 3 levels deep, checks audio file paths,
    and returns the most common pattern found.

    Returns:
        Pattern string like "{artist}/{album}/{number:02d} - {title}.flac"
        or None if no pattern could be detected.
    """
    root = Path(root_dir)
    if not root.is_dir():
        return None

    patterns = Counter()

    for dirpath, dirnames, filenames in os.walk(root):
        # Limit depth to 3 levels
        depth = Path(dirpath).relative_to(root).parts
        if len(depth) > 3:
            dirnames.clear()
            continue

        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext not in AUDIO_EXTENSIONS:
                continue

            rel_path = Path(dirpath, fname).relative_to(root)
            pattern = _classify_path(rel_path)
            if pattern:
                patterns[pattern] += 1

    if not patterns:
        return None

    # Return the most common pattern
    best_pattern, count = patterns.most_common(1)[0]
    logger.info("Detected library pattern '%s' (%d files matched)", best_pattern, count)
    return best_pattern


def _classify_path(rel_path: Path) -> str | None:
    """Classify a relative file path into a naming pattern."""
    parts = rel_path.parts
    filename = parts[-1]
    ext = Path(filename).suffix

    if len(parts) == 3:
        # artist/album/track.ext
        if re.match(r"^\d{1,2}\s*[-._]\s*.+", filename):
            return "{artist}/{album}/{number:02d} - {title}" + ext
        elif re.match(r"^\d{1,2}\s+.+", filename):
            return "{artist}/{album}/{number:02d} {title}" + ext
        else:
            return "{artist}/{album}/{title}" + ext

    elif len(parts) == 2:
        # album/track.ext (flat artist structure or single-artist library)
        if re.match(r"^\d{1,2}\s*[-._]\s*.+", filename):
            return "{album}/{number:02d} - {title}" + ext
        else:
            return "{album}/{title}" + ext

    return None


def generate_path(root_dir: str, pattern: str, metadata: dict) -> str:
    """Generate a full output file path from a pattern and track metadata.

    Args:
        root_dir: Library root directory
        pattern: Pattern string with {artist}, {album}, {title}, {number}, {year}, {genre} placeholders
        metadata: Dict with keys matching the placeholder names

    Returns:
        Full file path string.
    """
    # Sanitize values for filesystem safety
    safe = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            safe[key] = _sanitize_filename(value)
        elif isinstance(value, int) and key == "number":
            safe[key] = value
        else:
            safe[key] = value

    try:
        relative = pattern.format(**safe)
    except (KeyError, ValueError) as e:
        logger.warning("Pattern format error: %s (pattern=%s, metadata=%s)", e, pattern, metadata)
        # Fallback: use basic artist/album/track structure
        artist = safe.get("artist", "Unknown Artist")
        album = safe.get("album", "Unknown Album")
        title = safe.get("title", "Unknown")
        number = safe.get("number", 0)
        relative = f"{artist}/{album}/{number:02d} - {title}.flac"

    return os.path.join(root_dir, relative)


def ensure_directory(file_path: str) -> None:
    """Create parent directories for a file path if they don't exist."""
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    """Remove or replace characters that are unsafe in file/directory names."""
    # Replace path separators and other problematic characters
    unsafe = r'<>:"/\|?*'
    for char in unsafe:
        name = name.replace(char, "_")
    # Remove leading/trailing whitespace and dots
    name = name.strip().strip(".")
    return name or "Unknown"
