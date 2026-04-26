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
        pattern: Pattern string with {artist}, {album}, {title}, {number}, {year}, {genre}, {disc} placeholders
        metadata: Dict with keys matching the placeholder names

    Returns:
        Full file path string.
    """
    # Sanitize values for filesystem safety
    safe = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            safe[key] = _sanitize_filename(value)
        elif isinstance(value, int) and key in ("number", "disc", "total_discs"):
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
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        logger.error(f"Permission denied creating directory for {file_path}: {e}")
        raise RuntimeError(f"Permission denied: Cannot create directory. Check if the output directory is mounted and writable.") from e
    except OSError as e:
        logger.error(f"Failed to create directory for {file_path}: {e}")
        raise RuntimeError(f"Cannot create output directory. Check if the path exists and is accessible.") from e


def _sanitize_filename(name: str) -> str:
    """Remove or replace characters that are unsafe in file/directory names."""
    # Replace path separators and other problematic characters
    unsafe = r'<>:"/\|?*'
    for char in unsafe:
        name = name.replace(char, "_")
    # Remove leading/trailing whitespace and dots
    name = name.strip().strip(".")
    return name or "Unknown"


def validate_output_directory(output_dir: str) -> bool:
    """Check if the output directory exists and is writable.

    Args:
        output_dir: Path to check

    Returns:
        True if directory is accessible and writable

    Raises:
        RuntimeError: If directory is not accessible
    """
    if not output_dir:
        return False  # No output directory configured

    path = Path(output_dir)

    # Check if directory exists
    if not path.exists():
        raise RuntimeError(
            f"Output directory does not exist: {output_dir}\n"
            f"For network shares, make sure the volume is mounted."
        )

    # Check if it's a directory
    if not path.is_dir():
        raise RuntimeError(
            f"Output path is not a directory: {output_dir}"
        )

    # Check if it's writable
    if not os.access(output_dir, os.W_OK):
        raise RuntimeError(
            f"Output directory is not writable: {output_dir}\n"
            f"Check permissions and mount status."
        )

    logger.info(f"Output directory validated: {output_dir}")
    return True
