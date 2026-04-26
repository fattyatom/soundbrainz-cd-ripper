import hashlib
import logging
import os
import sys
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


def _unmount_device(device: str) -> None:
    """Unmount the CD device before ripping to prevent resource busy errors."""
    # Convert /dev/rdiskX -> /dev/diskX for diskutil
    regular_device = device.replace('/dev/rdisk', '/dev/disk')
    try:
        subprocess.run(
            ['diskutil', 'unmountDisk', regular_device],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        logger.info("_unmount_device: Successfully unmounted %s", regular_device)
    except Exception as e:
        logger.warning("_unmount_device: Could not unmount disk: %s", str(e))


def _remount_device(device: str) -> None:
    """Remount the CD device after ripping to restore normal system behavior."""
    if sys.platform != "darwin":
        # Only macOS needs remounting - Linux systems handle this automatically
        return

    # Convert /dev/rdiskX -> /dev/diskX for diskutil
    regular_device = device.replace('/dev/rdisk', '/dev/disk')
    try:
        # Attempt to remount the disk to restore normal system behavior
        subprocess.run(
            ['diskutil', 'mountDisk', regular_device],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        logger.info("_remount_device: Successfully remounted %s", regular_device)
    except Exception as e:
        logger.warning("_remount_device: Could not remount disk: %s", str(e))
        # Try alternative approach - force the disk to be recognized again
        try:
            subprocess.run(
                ['diskutil', 'resetUserPermissions', regular_device],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            logger.info("_remount_device: Reset permissions for %s", regular_device)
        except Exception as e2:
            logger.warning("_remount_device: Could not reset permissions: %s", str(e2))


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


def _calculate_sha256(file_path: str) -> str:
    """Calculate SHA-256 checksum of a file.

    Args:
        file_path: Path to the file to checksum

    Returns:
        Hexadecimal SHA-256 checksum string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _get_cdparanoia_flags(quality_preset: str) -> list:
    """Generate cdparanoia flags based on quality preset.

    Args:
        quality_preset: One of "audiophile", "portable", "archive", "custom"

    Returns:
        List of cdparanoia command-line flags
    """
    flags = ["-v"]  # Always verbose for diagnostics

    if quality_preset == "audiophile":
        # Slowest speed, maximum error recovery
        flags.extend(["-S", "1", "-X", "-z"])  # 1x speed, abort on skip, never skip
    elif quality_preset == "archive":
        # Medium speed, high error recovery
        flags.extend(["-S", "8", "-X", "-z"])  # 8x speed, abort on skip, never skip
    # portable uses defaults (no additional flags)

    return flags


def _check_cdparanoia_warnings(stderr: str) -> None:
    """Parse cdparanoia stderr for error indicators and log warnings.

    Even if cdparanoia returns exit code 0, it may have encountered errors
    that it partially recovered from. This function detects and logs those.

    Args:
        stderr: Standard error output from cdparanoia

    Raises:
        RuntimeError: If abort_on_skip is enabled and errors are detected
    """
    error_indicators = [";-(", "8-X", ":-0", ":-("]
    warning_indicators = ["8-|", ":-/", ":-P", "V"]

    errors_found = []
    warnings_found = []

    for line in stderr.split('\n'):
        for indicator in error_indicators:
            if indicator in line:
                errors_found.append(line.strip())
        for indicator in warning_indicators:
            if indicator in line:
                warnings_found.append(line.strip())

    if warnings_found:
        logger.warning("_check_cdparanoia_warnings: Detected %d warnings:", len(warnings_found))
        for warning in warnings_found[:10]:  # Limit to first 10
            logger.warning("_check_cdparanoia_warnings: %s", warning)

    if errors_found:
        logger.error("_check_cdparanoia_warnings: Detected %d errors:", len(errors_found))
        for error in errors_found[:10]:  # Limit to first 10
            logger.error("_check_cdparanoia_warnings: %s", error)
        raise RuntimeError(f"cdparanoia detected {len(errors_found)} unrecoverable errors")

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
_rip_thread = None  # Track thread to prevent multiple simultaneous rips


def get_status() -> dict:
    """Return a copy of the current rip state (thread-safe)."""
    with _rip_lock:
        return dict(rip_state)


def is_active() -> bool:
    with _rip_lock:
        return rip_state["active"]


def start_rip(device: str, release: Optional[dict] = None, output_dir: Optional[str] = None, selected_tracks: Optional[list[int]] = None) -> dict:
    """Start a rip job in a background thread.

    Args:
        device: CD drive device path (e.g., /dev/sr0)
        release: Optional MusicBrainz release metadata for tagging
        output_dir: Final output directory (from config). If None, uses temp dir only.
        selected_tracks: Optional list of track numbers to rip. If None, rips all tracks.

    Returns:
        Current rip state dict.
    """
    global _rip_thread

    logger.info("start_rip: Starting rip for device %s", device)
    logger.info("start_rip: Release: %s", release.get("album") if release else "None")
    logger.info("start_rip: Output dir: %s", output_dir)

    with _rip_lock:
        if rip_state["active"]:
            # Check if the thread is actually still alive
            if _rip_thread and _rip_thread.is_alive():
                logger.warning("start_rip: Previous thread still alive, cannot start new rip")
                return {"error": "A rip is already in progress"}
            else:
                # Thread died but left active=True, clean it up
                logger.warning("start_rip: Previous thread died but state not cleaned, resetting")
                rip_state["active"] = False

        # Clear state and initialize
        rip_state.update({
            "active": True,
            "phase": "starting",
            "track": 0,
            "total_tracks": 0,
            "percent": 0,
            "error": None,
            "output_dir": output_dir,
        })

    # Create regular (non-daemon) thread to prevent premature termination
    logger.info("start_rip: Creating new thread")
    _rip_thread = threading.Thread(
        target=_rip_worker_with_cleanup,
        args=(device, release, output_dir, selected_tracks),
        daemon=False,  # Keep thread alive
    )

    logger.info("start_rip: Starting thread")
    _rip_thread.start()
    logger.info("start_rip: Thread started successfully")

    status = get_status()
    logger.info("start_rip: Returning status: %s", status)
    return status


def _check_dependencies() -> None:
    """Check if required tools are available and raise clear errors."""
    logger.info("_check_dependencies: Starting dependency check")
    try:
        # Test cdparanoia
        cmd = _find_cdparanoia()
        logger.info("_check_dependencies: Found cdparanoia command: %s", cmd)
        result = subprocess.run(
            [cmd, "-V"],
            capture_output=True,
            timeout=5
        )
        logger.info("_check_dependencies: cdparanoia -V returned %d", result.returncode)
        if result.returncode != 0:
            raise RuntimeError(f"{cmd} not found or not working")

        # Test ffmpeg
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5
        )
        logger.info("_check_dependencies: ffmpeg -version returned %d", result.returncode)
        if result.returncode != 0:
            raise RuntimeError("ffmpeg not found or not working")

        logger.info("_check_dependencies: All dependencies OK")

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("_check_dependencies: Dependency check failed: %s", str(e))
        tools = []
        if not shutil.which("cd-paranoia") and not shutil.which("cdparanoia"):
            tools.append("cdparanoia")
        if not shutil.which("ffmpeg"):
            tools.append("ffmpeg")
        raise RuntimeError(f"Missing dependencies: {', '.join(tools)}. Install with: brew install {' '.join(tools)}")


def _rip_worker_with_cleanup(device: str, release: Optional[dict], output_dir: Optional[str], selected_tracks: Optional[list[int]] = None) -> None:
    """Worker function with proper cleanup and exception handling."""
    logger.info("_rip_worker_with_cleanup: Worker started")
    try:
        logger.info("_rip_worker_with_cleanup: Checking dependencies")
        _check_dependencies()
        logger.info("_rip_worker_with_cleanup: Dependencies OK, starting rip worker")
        _rip_worker(device, release, output_dir, selected_tracks)
        logger.info("_rip_worker_with_cleanup: Rip worker completed successfully")

        # Auto-eject disc after successful rip if configured
        try:
            config = _get_config()()
            if config.get("auto_eject", True):
                logger.info("_rip_worker_with_cleanup: Auto-eject enabled, ejecting disc")
                from backend.services.drive_service import eject_disc
                if eject_disc(device):
                    logger.info("_rip_worker_with_cleanup: Successfully ejected disc")
                else:
                    logger.warning("_rip_worker_with_cleanup: Failed to eject disc")
            else:
                logger.info("_rip_worker_with_cleanup: Auto-eject disabled in config")
        except Exception as e:
            logger.warning("_rip_worker_with_cleanup: Error during auto-eject: %s", str(e))

    except Exception as e:
        logger.error("_rip_worker_with_cleanup: Exception occurred: %s", str(e))
        logger.exception("_rip_worker_with_cleanup: Full exception traceback")
        with _rip_lock:
            rip_state["phase"] = "error"
            rip_state["error"] = str(e)
    finally:
        logger.info("_rip_worker_with_cleanup: Remounting device to restore normal system behavior")
        try:
            _remount_device(device)
        except Exception as e:
            logger.error("_rip_worker_with_cleanup: Failed to remount device: %s", str(e))

        logger.info("_rip_worker_with_cleanup: Worker finishing, setting active=False")
        with _rip_lock:
            rip_state["active"] = False


def _rip_worker(device: str, release: Optional[dict], output_dir: Optional[str], selected_tracks: Optional[list[int]] = None) -> None:
    """Background worker that runs the full rip pipeline:
    1. Rip CD to WAV (cdparanoia)
    2. Transcode WAV to FLAC (ffmpeg)
    3. Organize files into library folder
    """
    temp_dir = tempfile.mkdtemp(prefix="soundbrainz_")
    flac_dir = tempfile.mkdtemp(prefix="soundbrainz_flac_")
    _moved_to_library = False

    logger.info("Rip worker started for device: %s", device)
    logger.info("Temp directory: %s", temp_dir)

    try:
        # Phase 1: Rip CD to WAV
        with _rip_lock:
            rip_state["phase"] = "ripping"

        logger.info("Starting CD rip with cdparanoia...")
        wav_files = rip_disc(device, temp_dir, _update_rip_progress, selected_tracks)
        logger.info("Completed ripping %d tracks", len(wav_files))

        # Generate checksum file if checksums were calculated
        with _rip_lock:
            checksums = rip_state.get("checksums", {})

        if checksums:
            checksum_file = os.path.join(temp_dir, "checksums.txt")
            with open(checksum_file, "w") as f:
                f.write(f"# SHA-256 checksums for ripped tracks\n")
                f.write(f"# Generated: {__import__('datetime').datetime.now().isoformat()}\n")
                for track_num, checksum in sorted(checksums.items()):
                    f.write(f"Track {track_num}: {checksum}\n")
            logger.info("Wrote checksums to %s", checksum_file)

        # Phase 2: Download cover art if we have release metadata
        cover_art_path = None
        if release and release.get("mbid"):
            download_cover_art = _get_coverart()
            cover_path = os.path.join(temp_dir, "cover.jpg")
            if download_cover_art(release["mbid"], cover_path):
                cover_art_path = cover_path

        # Phase 3: Transcode with format awareness
        with _rip_lock:
            rip_state["phase"] = "transcoding"
            rip_state["percent"] = 0

        # Load audio format configuration
        config = _get_config()()
        audio_format = config.get("audio_format", "aiff")
        flac_compression = config.get("flac_compression_level", 5)

        track_metadata_list = _build_track_metadata(release)

        # Transcode all formats (FLAC, AIFF, WAV) to ensure metadata and cover art are embedded
        transcode_album = _get_transcoder()
        output_files = transcode_album(
            temp_dir, flac_dir, track_metadata_list,
            cover_art_path=cover_art_path,
            progress_callback=_update_transcode_progress,
            audio_format=audio_format,
            flac_compression_level=flac_compression,
        )

        # Phase 4: Organize into library
        with _rip_lock:
            rip_state["phase"] = "organizing"
            rip_state["percent"] = 0

        final_dir = output_dir
        if not final_dir:
            config = _get_config()()
            final_dir = config.get("output_dir")

        if final_dir and release:
            generate_path, ensure_directory = _get_library()
            config = _get_config()()

            # Use multi-disc pattern if this is a multi-disc release
            total_discs = release.get("total_discs", 1)
            if total_discs > 1:
                pattern = config.get("folder_pattern_multi_disc", "{artist}/{album}/CD{disc}/{number:02d} - {title}.flac")
                logger.info("Using multi-disc pattern: %s", pattern)
            else:
                pattern = config.get("folder_pattern", "{artist}/{album}/{number:02d} - {title}.flac")
                logger.info("Using single-disc pattern: %s", pattern)

            for i, output_path in enumerate(output_files):
                track_meta = track_metadata_list[i] if i < len(track_metadata_list) else {}
                # Add file extension to track metadata for path generation
                track_meta["ext"] = audio_format
                dest = generate_path(final_dir, pattern, track_meta)
                ensure_directory(dest)
                shutil.move(output_path, dest)
                logger.info("Moved %s -> %s", output_path, dest)

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
            with _rip_lock:
                rip_state["output_dir"] = flac_dir
            logger.info("No output dir configured, FLAC files at: %s", flac_dir)

        # Done
        with _rip_lock:
            rip_state["phase"] = "done"
            rip_state["percent"] = 100
        logger.info("Rip pipeline complete")

    except Exception as e:
        with _rip_lock:
            rip_state["phase"] = "error"
            rip_state["error"] = str(e)
        logger.exception("Rip failed")
        shutil.rmtree(flac_dir, ignore_errors=True)
    finally:
        # Clean up temp WAV directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        # Clean up flac_dir only when files were moved to the library
        # (if no library, flac_dir is the output and must be kept)
        if _moved_to_library:
            shutil.rmtree(flac_dir, ignore_errors=True)


def _update_rip_progress(track: int, total_tracks: int, percent: int) -> None:
    """Callback for rip progress updates (thread-safe)."""
    with _rip_lock:
        rip_state["track"] = track
        rip_state["total_tracks"] = total_tracks
        rip_state["percent"] = percent


def _update_transcode_progress(track: int, total_tracks: int, percent: int) -> None:
    """Callback for transcode progress updates (thread-safe)."""
    with _rip_lock:
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

    # Include disc information for multi-disc releases
    disc_number = release.get("disc_number", 1)
    total_discs = release.get("total_discs", 1)

    metadata_list = []
    for track in release["tracks"]:
        metadata_list.append({
            "artist": track.get("artist", album_artist),
            "album_artist": album_artist,
            "album": album,
            "title": track.get("title", "Unknown"),
            "number": track.get("number", 0),
            "track": f"{track.get('number', 0)}/{total}",
            "disc": disc_number,
            "total_discs": total_discs,
            "date": year,
            "genre": "",
        })
    return metadata_list


def rip_disc(device: str, output_dir: str, progress_callback: Callable, selected_tracks: Optional[list[int]] = None) -> list[str]:
    """Rip tracks from a CD using cdparanoia.

    Args:
        device: CD drive device path
        output_dir: Directory to write WAV files to
        progress_callback: Called with (track, total_tracks, percent)
        selected_tracks: Optional list of track numbers to rip. If None, rips all tracks.

    Returns:
        List of output WAV file paths.
    """
    logger.info("rip_disc: Starting rip for device %s to %s", device, output_dir)

    # First, get track count from cdparanoia -Q (query)
    total_tracks = _get_track_count(device)
    if total_tracks == 0:
        raise RuntimeError("No audio tracks found on disc")

    logger.info("rip_disc: Found %d tracks on disc", total_tracks)

    # Determine which tracks to rip
    if selected_tracks:
        # Validate and filter selected tracks
        selected_tracks = [t for t in selected_tracks if 1 <= t <= total_tracks]
        if not selected_tracks:
            raise RuntimeError("No valid tracks selected")
        tracks_to_rip = sorted(selected_tracks)
        logger.info("rip_disc: Ripping %d selected tracks: %s", len(tracks_to_rip), tracks_to_rip)
    else:
        tracks_to_rip = list(range(1, total_tracks + 1))
        logger.info("rip_disc: Ripping all %d tracks", total_tracks)

    progress_callback(0, len(tracks_to_rip), 0)

    output_files = []
    for i, track_num in enumerate(tracks_to_rip):
        logger.info("rip_disc: Ripping track %d/%d (track %d on disc)", i + 1, len(tracks_to_rip), track_num)
        output_path = Path(output_dir) / f"track{track_num:02d}.wav"
        _rip_single_track(device, track_num, str(output_path))
        output_files.append(str(output_path))

        pct = int(((i + 1) / len(tracks_to_rip)) * 100)
        progress_callback(i + 1, len(tracks_to_rip), pct)
        logger.info("rip_disc: Completed track %d/%d (%d%%)", i + 1, len(tracks_to_rip), pct)

    logger.info("rip_disc: Completed all %d tracks", len(output_files))
    return output_files


def _get_track_count(device: str) -> int:
    """Query the disc for number of audio tracks."""
    # Ensure device is unmounted first
    _unmount_device(device)

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
    """Rip a single track using cdparanoia with proper error correction."""
    cmd = _find_cdparanoia()
    logger.info("_rip_single_track: Ripping track %d with %s", track_num, cmd)

    # Get quality preset for flag selection
    config = _get_config()()
    quality_preset = config.get("quality_preset", "audiophile")
    flags = _get_cdparanoia_flags(quality_preset)
    logger.info("_rip_single_track: Using quality preset '%s' with flags: %s", quality_preset, flags)

    # Ensure device is unmounted first (prevents timeouts)
    _unmount_device(device)

    try:
        # Build command with quality-aware flags
        # Syntax: cdparanoia [flags] -d device track_number output_file
        result = subprocess.run(
            [cmd] + flags + ["-d", device, str(track_num), output_path],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes per track
        )

        if result.returncode != 0:
            logger.error("_rip_single_track: cdparanoia failed (exit %d)", result.returncode)
            logger.error("_rip_single_track: stderr: %s", result.stderr[:500])
            raise RuntimeError(f"cdparanoia failed on track {track_num}: {result.stderr[:200]}")

        # Check for warnings even on successful rips
        if result.stderr:
            _check_cdparanoia_warnings(result.stderr)

        # Validate output file
        if not os.path.exists(output_path):
            raise RuntimeError(f"cdparanoia did not create output file for track {track_num}")

        file_size = os.path.getsize(output_path)
        if file_size == 0:
            raise RuntimeError(f"cdparanoia created empty file for track {track_num}")

        # Calculate SHA-256 checksum for integrity verification
        checksum = _calculate_sha256(output_path)
        logger.info("_rip_single_track: SHA-256 checksum for track %d: %s", track_num, checksum)

        # Store checksum in rip_state for later file generation
        with _rip_lock:
            if "checksums" not in rip_state:
                rip_state["checksums"] = {}
            rip_state["checksums"][track_num] = checksum

        logger.info("_rip_single_track: Successfully ripped track %d to %s (%d bytes)",
                    track_num, output_path, file_size)

    except subprocess.TimeoutExpired:
        logger.error("_rip_single_track: cdparanoia timed out ripping track %d", track_num)
        raise RuntimeError(f"Timed out ripping track {track_num}")
