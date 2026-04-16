import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def _find_cdparanoia() -> str:
    """Find the cdparanoia binary. On macOS, libcdio provides 'cd-paranoia' (with hyphen).
    On Linux, it's typically 'cdparanoia' (no hyphen).

    Returns:
        The command name to use.
    Raises:
        RuntimeError if neither is found.
    """
    import shutil as _shutil
    # Try cd-paranoia first (macOS via brew install libcdio-paranoia)
    if _shutil.which("cd-paranoia"):
        return "cd-paranoia"
    # Then try cdparanoia (Linux, or older macOS installs)
    if _shutil.which("cdparanoia"):
        return "cdparanoia"
    raise RuntimeError(
        "No CD ripping tool found. Install one of:\n"
        "  macOS:  brew install libcdio-paranoia\n"
        "  Linux:  apt install cdparanoia"
    )


# Lazy imports to avoid circular dependencies
def _get_transcoder():
    from backend.services.transcoder_service import transcode_album
    return transcode_album

def _get_coverart():
    from backend.services.coverart_service import download_cover_art
    return download_cover_art

def _get_library():
    from backend.services.library_service import generate_path, ensure_directory
    return generate_path, ensure_directory

def _get_config():
    from backend.config import load_config
    return load_config

# Global rip state — single rip at a time
rip_state = {
    "active": False,
    "phase": "idle",      # idle, ripping, transcoding, organizing, done, error
    "track": 0,
    "total_tracks": 0,
    "percent": 0,
    "error": None,
    "output_dir": None,
}

_rip_lock = threading.Lock()


def get_status() -> dict:
    """Return a copy of the current rip state."""
    return dict(rip_state)


def is_active() -> bool:
    return rip_state["active"]


def start_rip(device: str, release: Optional[dict] = None, output_dir: Optional[str] = None) -> dict:
    """Start a rip job in a background thread.

    Args:
        device: CD drive device path (e.g., /dev/sr0)
        release: Optional MusicBrainz release metadata for tagging
        output_dir: Final output directory (from config). If None, uses temp dir only.

    Returns:
        Current rip state dict.
    """
    with _rip_lock:
        if rip_state["active"]:
            return {"error": "A rip is already in progress"}

        rip_state.update({
            "active": True,
            "phase": "ripping",
            "track": 0,
            "total_tracks": 0,
            "percent": 0,
            "error": None,
            "output_dir": output_dir,
        })

    thread = threading.Thread(
        target=_rip_worker,
        args=(device, release, output_dir),
        daemon=True,
    )
    thread.start()
    return get_status()


def _rip_worker(device: str, release: Optional[dict], output_dir: Optional[str]) -> None:
    """Background worker that runs the full rip pipeline:
    1. Rip CD to WAV (cdparanoia)
    2. Transcode WAV to FLAC (ffmpeg)
    3. Organize files into library folder
    """
    temp_dir = tempfile.mkdtemp(prefix="soundbrainz_")
    flac_dir = tempfile.mkdtemp(prefix="soundbrainz_flac_")
    _moved_to_library = False
    try:
        # Phase 1: Rip CD to WAV
        rip_state["phase"] = "ripping"
        wav_files = rip_disc(device, temp_dir, _update_rip_progress)

        # Phase 2: Download cover art if we have release metadata
        cover_art_path = None
        if release and release.get("mbid"):
            download_cover_art = _get_coverart()
            cover_path = os.path.join(temp_dir, "cover.jpg")
            if download_cover_art(release["mbid"], cover_path):
                cover_art_path = cover_path

        # Phase 3: Transcode WAV to FLAC
        rip_state["phase"] = "transcoding"
        rip_state["percent"] = 0

        track_metadata_list = _build_track_metadata(release)
        transcode_album = _get_transcoder()
        flac_files = transcode_album(
            temp_dir, flac_dir, track_metadata_list,
            cover_art_path=cover_art_path,
            progress_callback=_update_transcode_progress,
        )

        # Phase 4: Organize into library
        rip_state["phase"] = "organizing"
        rip_state["percent"] = 0

        final_dir = output_dir
        if not final_dir:
            config = _get_config()()
            final_dir = config.get("output_dir")

        if final_dir and release:
            generate_path, ensure_directory = _get_library()
            config = _get_config()()
            pattern = config.get("folder_pattern", "{artist}/{album}/{number:02d} - {title}.flac")

            for i, flac_path in enumerate(flac_files):
                track_meta = track_metadata_list[i] if i < len(track_metadata_list) else {}
                dest = generate_path(final_dir, pattern, track_meta)
                ensure_directory(dest)
                shutil.move(flac_path, dest)
                logger.info("Moved %s -> %s", flac_path, dest)

            # Also copy cover art to the album folder if available
            if cover_art_path and track_metadata_list:
                first_track_dest = generate_path(final_dir, pattern, track_metadata_list[0])
                album_dir = str(Path(first_track_dest).parent)
                cover_dest = os.path.join(album_dir, "cover.jpg")
                if not os.path.exists(cover_dest):
                    shutil.copy2(cover_art_path, cover_dest)

            _moved_to_library = True
        else:
            # No library dir configured or no metadata — leave FLACs in flac_dir
            # Record the path so the caller can find the files
            rip_state["output_dir"] = flac_dir
            logger.info("No output dir configured, FLAC files at: %s", flac_dir)

        # Done
        rip_state["phase"] = "done"
        rip_state["percent"] = 100
        logger.info("Rip pipeline complete")

    except Exception as e:
        logger.exception("Rip failed")
        rip_state["phase"] = "error"
        rip_state["error"] = str(e)
        shutil.rmtree(flac_dir, ignore_errors=True)
    finally:
        rip_state["active"] = False
        # Clean up temp WAV directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        # Clean up flac_dir only when files were moved to the library
        # (if no library, flac_dir is the output and must be kept)
        if _moved_to_library:
            shutil.rmtree(flac_dir, ignore_errors=True)


def _update_rip_progress(track: int, total_tracks: int, percent: int) -> None:
    """Callback for rip progress updates."""
    rip_state["track"] = track
    rip_state["total_tracks"] = total_tracks
    rip_state["percent"] = percent


def _update_transcode_progress(track: int, total_tracks: int, percent: int) -> None:
    """Callback for transcode progress updates."""
    rip_state["track"] = track
    rip_state["total_tracks"] = total_tracks
    rip_state["percent"] = percent


def _build_track_metadata(release: Optional[dict]) -> list[dict]:
    """Build per-track metadata dicts from a MusicBrainz release."""
    if not release or not release.get("tracks"):
        return []

    album_artist = release.get("artist", "Unknown Artist")
    album = release.get("album", "Unknown Album")
    year = release.get("year", "")
    total = len(release["tracks"])

    metadata_list = []
    for track in release["tracks"]:
        metadata_list.append({
            "artist": track.get("artist", album_artist),
            "album_artist": album_artist,
            "album": album,
            "title": track.get("title", "Unknown"),
            "number": track.get("number", 0),
            "track": f"{track.get('number', 0)}/{total}",
            "date": year,
            "genre": "",
        })
    return metadata_list


def rip_disc(device: str, output_dir: str, progress_callback: Callable) -> list[str]:
    """Rip all tracks from a CD using cdparanoia.

    Args:
        device: CD drive device path
        output_dir: Directory to write WAV files to
        progress_callback: Called with (track, total_tracks, percent)

    Returns:
        List of output WAV file paths.
    """
    # First, get track count from cdparanoia -Q (query)
    total_tracks = _get_track_count(device)
    if total_tracks == 0:
        raise RuntimeError("No audio tracks found on disc")

    progress_callback(0, total_tracks, 0)

    output_files = []
    for track_num in range(1, total_tracks + 1):
        output_path = Path(output_dir) / f"track{track_num:02d}.wav"
        _rip_single_track(device, track_num, str(output_path))
        output_files.append(str(output_path))

        pct = int((track_num / total_tracks) * 100)
        progress_callback(track_num, total_tracks, pct)

    return output_files


def _get_track_count(device: str) -> int:
    """Query the disc for number of audio tracks."""
    cmd = _find_cdparanoia()
    try:
        result = subprocess.run(
            [cmd, "-d", device, "-Q"],
            capture_output=True, text=True, timeout=30
        )
        # cdparanoia -Q outputs track info on stderr
        return _parse_track_count(result.stderr)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Timed out querying disc")


def _parse_track_count(stderr: str) -> int:
    """Parse cdparanoia -Q stderr output to get track count.

    The output contains lines like:
      1.        0 [04:02.25]    0        [audio]
      2.    18175 [03:55.50]    18175    [audio]
    """
    count = 0
    for line in stderr.splitlines():
        line = line.strip()
        # Match lines starting with a track number followed by a period
        if re.match(r"^\d+\.\s", line):
            count += 1
    return count


def _rip_single_track(device: str, track_num: int, output_path: str) -> None:
    """Rip a single track using cdparanoia or cd-paranoia."""
    cmd = _find_cdparanoia()
    try:
        result = subprocess.run(
            [cmd, "-d", device, str(track_num), output_path],
            capture_output=True, text=True, timeout=600  # 10 min timeout per track
        )
        if result.returncode != 0:
            raise RuntimeError(f"{cmd} failed on track {track_num}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timed out ripping track {track_num}")
