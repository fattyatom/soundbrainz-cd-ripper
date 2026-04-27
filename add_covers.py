#!/usr/bin/env python3
"""
One-time script to add album covers to existing audio files.
Embeds cover art during re-encoding to preserve metadata.
"""

import subprocess
import sys
from pathlib import Path

# Extensions to process
AUDIO_EXTENSIONS = {'.flac', '.aiff', '.wav'}
COVER_NAMES = {'cover.jpg', 'cover.jpeg', 'cover.png', 'folder.jpg', 'front.jpg'}


def find_cover_art(directory: Path) -> Path | None:
    """Find cover art image in directory."""
    for cover_name in COVER_NAMES:
        cover_path = directory / cover_name
        if cover_path.exists():
            return cover_path
    return None


def embed_cover_art_flac(audio_path: Path, cover_path: Path) -> bool:
    """Embed cover art into FLAC file using metaflac or ffmpeg."""
    # Try metaflac first (faster, no re-encoding)
    try:
        result = subprocess.run(
            ["metaflac", f"--import-picture-from={cover_path}", str(audio_path)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass  # metaflac not installed, use ffmpeg

    # Fallback to ffmpeg (re-encodes with cover art)
    return reencode_with_cover(audio_path, cover_path, "flac")


def reencode_with_cover(audio_path: Path, cover_path: Path, audio_format: str) -> bool:
    """Re-encode audio file with cover art embedded."""
    temp_output = audio_path.with_suffix(f".tmp.{audio_format}")

    # Build ffmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-i", str(cover_path),
        "-map", "0:a",
        "-map", "1:v",
        "-c:a", "copy" if audio_format == "flac" else "pcm_s16be" if audio_format == "aiff" else "pcm_s16le",
        "-disposition:v", "attached_pic",
        "-metadata:s:v", "comment=Cover (front)",
    ]

    # Add format-specific options
    if audio_format == "flac":
        cmd.extend(["-compression_level", "5"])
    elif audio_format in ("aiff", "wav"):
        cmd.extend(["-id3v2_version", "3", "-write_id3v2", "1"])
        cmd.extend(["-metadata:s:v", "title=Album cover"])

    cmd.append(str(temp_output))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            # Replace original with temp file
            temp_output.replace(audio_path)
            return True
        else:
            print(f"  ERROR: ffmpeg failed: {result.stderr[:200]}")
            temp_output.unlink(missing_ok=True)
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  ERROR: {e}")
        temp_output.unlink(missing_ok=True)
        return False


def find_directories_with_audio_and_cover(root: Path) -> list[Path]:
    """Recursively find all directories containing both audio files and cover art."""
    directories = []

    for item in root.rglob('*'):
        if item.is_dir():
            # Check if this directory has audio files
            audio_files = [f for f in item.iterdir() if f.suffix.lower() in AUDIO_EXTENSIONS]
            if audio_files:
                # Check if this directory has cover art
                cover = find_cover_art(item)
                if cover:
                    directories.append(item)

    return directories


def process_directory(directory: Path) -> int:
    """Process all audio files in directory. Returns count of processed files."""
    print(f"\n📁 Processing: {directory}")

    # Find cover art
    cover_path = find_cover_art(directory)
    if not cover_path:
        print(f"  ⚠️  No cover art found (looking for: {', '.join(COVER_NAMES)})")
        return 0

    print(f"  🖼️  Found cover: {cover_path.name}")

    # Find all audio files
    audio_files = [f for f in directory.iterdir() if f.suffix.lower() in AUDIO_EXTENSIONS]
    if not audio_files:
        print(f"  ⚠️  No audio files found")
        return 0

    print(f"  🎵 Found {len(audio_files)} audio file(s)")

    # Process each audio file
    success_count = 0
    for audio_file in sorted(audio_files):
        print(f"    Processing: {audio_file.name}")

        if audio_file.suffix.lower() == ".flac":
            success = embed_cover_art_flac(audio_file, cover_path)
        else:
            audio_format = audio_file.suffix.lower()[1:]  # Remove dot
            success = reencode_with_cover(audio_file, cover_path, audio_format)

        if success:
            print(f"    ✓ Success")
            success_count += 1
        else:
            print(f"    ✗ Failed")

    return success_count


def main():
    if len(sys.argv) < 2:
        print("Usage: python add_covers.py <directory1> [directory2] ...")
        print("\nExample:")
        print("  python add_covers.py '/Volumes/Music/02 CD Rip/久石譲' '/Volumes/Music/02 CD Rip/髙見優・吉川慶'")
        print("\nThe script will recursively find all directories containing both audio files and cover art,")
        print("then embed the cover art into the audio files.")
        sys.exit(1)

    root_directories = [Path(d) for d in sys.argv[1:]]

    total_count = 0
    for root_dir in root_directories:
        if not root_dir.exists():
            print(f"❌ Directory not found: {root_dir}")
            continue

        if not root_dir.is_dir():
            print(f"❌ Not a directory: {root_dir}")
            continue

        print(f"\n🔍 Scanning: {root_dir}")
        directories_to_process = find_directories_with_audio_and_cover(root_dir)

        if not directories_to_process:
            print(f"  ⚠️  No directories with both audio files and cover art found")
            continue

        print(f"  📂 Found {len(directories_to_process)} director(ies) to process")

        for directory in directories_to_process:
            count = process_directory(directory)
            total_count += count

    print(f"\n🎉 Done! Processed {total_count} file(s) total")


if __name__ == "__main__":
    main()
