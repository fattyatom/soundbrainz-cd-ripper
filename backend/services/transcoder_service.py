import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def wav_to_flac(input_path: str, output_path: str, metadata: Optional[dict] = None) -> str:
    """Convert a WAV file to FLAC using ffmpeg.

    Args:
        input_path: Path to input WAV file
        output_path: Path for output FLAC file
        metadata: Optional dict of metadata tags (artist, album, title, track, date, genre)

    Returns:
        Path to the output FLAC file.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:a", "flac",
        "-compression_level", "8",
    ]

    # Add metadata tags
    if metadata:
        tag_map = {
            "artist": "artist",
            "album": "album",
            "title": "title",
            "track": "track",       # "N/M" format
            "date": "date",
            "genre": "genre",
            "album_artist": "album_artist",
        }
        for key, ffmpeg_key in tag_map.items():
            value = metadata.get(key)
            if value:
                cmd.extend(["-metadata", f"{ffmpeg_key}={value}"])

    cmd.append(output_path)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr[:300]}")
        return output_path
    except FileNotFoundError:
        raise RuntimeError("ffmpeg is not installed. Install it with: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timed out transcoding {input_path}")


def embed_cover_art(flac_path: str, image_path: str) -> bool:
    """Embed cover art into a FLAC file using metaflac.

    Falls back to ffmpeg if metaflac is not available.

    Returns:
        True if successful, False otherwise.
    """
    # Try metaflac first (simpler and doesn't re-encode)
    try:
        result = subprocess.run(
            ["metaflac", f"--import-picture-from={image_path}", flac_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass  # metaflac not installed, try ffmpeg

    # Fallback: use ffmpeg to embed cover art
    try:
        temp_output = flac_path + ".tmp.flac"
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", flac_path,
                "-i", image_path,
                "-map", "0:a",
                "-map", "1",
                "-c", "copy",
                "-metadata:s:v", "comment=Cover (front)",
                "-disposition:v", "attached_pic",
                temp_output,
            ],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            Path(temp_output).replace(flac_path)
            return True
        else:
            Path(temp_output).unlink(missing_ok=True)
            logger.warning("ffmpeg cover art embedding failed: %s", result.stderr[:200])
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("Failed to embed cover art: %s", e)
        return False


def transcode_album(
    wav_dir: str,
    output_dir: str,
    track_metadata_list: list[dict],
    cover_art_path: Optional[str] = None,
    progress_callback=None,
) -> list[str]:
    """Transcode all WAV files in a directory to FLAC with metadata.

    Args:
        wav_dir: Directory containing WAV files (track01.wav, track02.wav, etc.)
        output_dir: Directory for output FLAC files
        track_metadata_list: List of metadata dicts, one per track
        cover_art_path: Optional path to cover art image to embed
        progress_callback: Optional callback(track, total, percent)

    Returns:
        List of output FLAC file paths.
    """
    wav_files = sorted(Path(wav_dir).glob("track*.wav"))
    total = len(wav_files)
    output_files = []

    for i, wav_file in enumerate(wav_files):
        # Get metadata for this track (by index)
        metadata = track_metadata_list[i] if i < len(track_metadata_list) else {}

        output_path = Path(output_dir) / wav_file.with_suffix(".flac").name
        wav_to_flac(str(wav_file), str(output_path), metadata)

        # Embed cover art if available
        if cover_art_path and Path(cover_art_path).exists():
            embed_cover_art(str(output_path), cover_art_path)

        output_files.append(str(output_path))

        if progress_callback:
            pct = int(((i + 1) / total) * 100)
            progress_callback(i + 1, total, pct)

    return output_files
