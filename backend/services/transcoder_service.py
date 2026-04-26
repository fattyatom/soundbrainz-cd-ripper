import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def transcode_audio(input_path: str, output_path: str,
                   audio_format: str, metadata: Optional[dict] = None,
                   flac_compression_level: int = 0) -> str:
    """Transcode WAV to target format with quality settings.

    Args:
        input_path: Path to input WAV file
        output_path: Path for output file (extension will be adjusted)
        audio_format: Target format ('flac', 'aiff', 'wav')
        metadata: Optional metadata dict
        flac_compression_level: Compression level for FLAC (0-12)

    Returns:
        Path to the output file.
    """
    # Adjust output extension based on format
    output_path = str(Path(output_path).with_suffix(f".{audio_format}"))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if audio_format == "flac":
        return _transcode_to_flac(input_path, output_path, metadata, flac_compression_level)
    elif audio_format == "aiff":
        return _transcode_to_aiff(input_path, output_path, metadata)
    elif audio_format == "wav":
        return _transcode_to_wav(input_path, output_path, metadata)
    else:
        raise ValueError(f"Unsupported format: {audio_format}")


def _transcode_to_flac(input_path: str, output_path: str,
                      metadata: Optional[dict], compression_level: int) -> str:
    """Transcode to FLAC with configurable compression and optimized parameters for dynamic content."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-bufsize", "2M",  # Larger buffer for dynamic content
        "-ar", "44100",    # Explicit sample rate
        "-ac", "2",        # Explicit channels (stereo)
        "-q:a", "0",       # Highest quality
        "-c:a", "flac",
        "-compression_level", str(compression_level),
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
        # Increased timeout for slower, higher-quality encoding (5 minutes instead of 2)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr[:300]}")
        return output_path
    except FileNotFoundError:
        raise RuntimeError("ffmpeg is not installed. Install it with: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timed out transcoding {input_path}")


def _transcode_to_aiff(input_path: str, output_path: str, metadata: Optional[dict]) -> str:
    """Transcode to AIFF (uncompressed, professional standard)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:a", "pcm_s16be",  # AIFF uses big-endian PCM
        "-ar", "44100",  # CD quality sample rate
        "-ac", "2",  # Stereo
    ]

    # Add metadata tags
    if metadata:
        cmd.extend(["-metadata", f"title={metadata.get('title', '')}"])
        cmd.extend(["-metadata", f"artist={metadata.get('artist', '')}"])
        cmd.extend(["-metadata", f"album={metadata.get('album', '')}"])
        cmd.extend(["-metadata", f"album_artist={metadata.get('album_artist', '')}"])
        cmd.extend(["-metadata", f"track={metadata.get('track', '')}"])
        cmd.extend(["-metadata", f"date={metadata.get('date', '')}"])
        cmd.extend(["-metadata", f"genre={metadata.get('genre', '')}"])

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


def _transcode_to_wav(input_path: str, output_path: str, metadata: Optional[dict]) -> str:
    """Transcode to WAV (uncompressed, universal compatibility)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:a", "pcm_s16le",  # WAV uses little-endian PCM
        "-ar", "44100",  # CD quality sample rate
        "-ac", "2",  # Stereo
    ]

    # Add metadata tags (WAV has limited metadata support, but we can try)
    if metadata:
        cmd.extend(["-metadata", f"title={metadata.get('title', '')}"])
        cmd.extend(["-metadata", f"artist={metadata.get('artist', '')}"])
        cmd.extend(["-metadata", f"album={metadata.get('album', '')}"])
        cmd.extend(["-metadata", f"album_artist={metadata.get('album_artist', '')}"])
        cmd.extend(["-metadata", f"track={metadata.get('track', '')}"])
        cmd.extend(["-metadata", f"date={metadata.get('date', '')}"])
        cmd.extend(["-metadata", f"genre={metadata.get('genre', '')}"])

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


def embed_cover_art_flac(flac_path: str, image_path: str) -> bool:
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


def embed_cover_art_aiff(aiff_path: str, image_path: str) -> bool:
    """Embed cover art into an AIFF file using ID3v2 tags.

    Args:
        aiff_path: Path to the AIFF file
        image_path: Path to the cover art image file

    Returns:
        True if successful, False otherwise.
    """
    try:
        temp_output = aiff_path + ".tmp.aiff"
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", aiff_path,
                "-i", image_path,
                "-map", "0:a",
                "-map", "1",
                "-c", "copy",
                "-id3v2_version", "3",
                "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (front)",
                "-disposition:v", "attached_pic",
                temp_output,
            ],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            Path(temp_output).replace(aiff_path)
            return True
        else:
            Path(temp_output).unlink(missing_ok=True)
            logger.warning("ffmpeg AIFF cover art embedding failed: %s", result.stderr[:200])
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("Failed to embed cover art in AIFF: %s", e)
        return False


def embed_cover_art_wav(wav_path: str, image_path: str) -> bool:
    """Embed cover art into a WAV file using ID3v2 tags.

    Args:
        wav_path: Path to the WAV file
        image_path: Path to the cover art image file

    Returns:
        True if successful, False otherwise.
    """
    try:
        temp_output = wav_path + ".tmp.wav"
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", wav_path,
                "-i", image_path,
                "-map", "0:a",
                "-map", "1",
                "-c", "copy",
                "-id3v2_version", "3",
                "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (front)",
                "-disposition:v", "attached_pic",
                temp_output,
            ],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            Path(temp_output).replace(wav_path)
            return True
        else:
            Path(temp_output).unlink(missing_ok=True)
            logger.warning("ffmpeg WAV cover art embedding failed: %s", result.stderr[:200])
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("Failed to embed cover art in WAV: %s", e)
        return False


def transcode_album(
    wav_dir: str,
    output_dir: str,
    track_metadata_list: list[dict],
    cover_art_path: Optional[str] = None,
    progress_callback=None,
    audio_format: str = "aiff",
    flac_compression_level: int = 0,
) -> list[str]:
    """Transcode all WAV files in a directory to target format with metadata.

    Args:
        wav_dir: Directory containing WAV files (track01.wav, track02.wav, etc.)
        output_dir: Directory for output files
        track_metadata_list: List of metadata dicts, one per track
        cover_art_path: Optional path to cover art image to embed
        progress_callback: Optional callback(track, total, percent)
        audio_format: Target audio format ('flac', 'aiff', 'wav')
        flac_compression_level: Compression level for FLAC (0-12)

    Returns:
        List of output file paths.
    """
    wav_files = sorted(Path(wav_dir).glob("track*.wav"))
    total = len(wav_files)
    output_files = []

    for i, wav_file in enumerate(wav_files):
        # Get metadata for this track (by index)
        metadata = track_metadata_list[i] if i < len(track_metadata_list) else {}

        # Use new format-aware transcoding
        output_path = Path(output_dir) / f"{wav_file.stem}.{audio_format}"
        transcode_audio(str(wav_file), str(output_path), audio_format,
                       metadata, flac_compression_level)

        # Embed cover art if available (all formats support embedded cover art)
        if cover_art_path and Path(cover_art_path).exists():
            if audio_format == "flac":
                embed_cover_art_flac(str(output_path), cover_art_path)
            elif audio_format == "aiff":
                embed_cover_art_aiff(str(output_path), cover_art_path)
            elif audio_format == "wav":
                embed_cover_art_wav(str(output_path), cover_art_path)

        output_files.append(str(output_path))

        if progress_callback:
            pct = int(((i + 1) / total) * 100)
            progress_callback(i + 1, total, pct)

    return output_files
