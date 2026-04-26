import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_drives() -> list[dict]:
    """Detect available CD/DVD drives on the system.

    Returns a list of dicts with keys: device, name, has_disc, drive_type.
    """
    if sys.platform == "darwin":
        return _detect_drives_macos()
    elif sys.platform == "linux":
        return _detect_drives_linux()
    else:
        logger.warning(f"Unsupported platform: {sys.platform}")
        return []


def eject_disc(device: str) -> bool:
    """Eject disc from the given device. Returns True on success."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["drutil", "eject"], check=True, capture_output=True)
        else:
            subprocess.run(["eject", device], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.exception(f"Failed to eject {device}")
        return False


def _detect_drives_macos() -> list[dict]:
    """Detect optical drives on macOS using system_profiler."""
    drives = []
    try:
        result = subprocess.run(
            ["system_profiler", "SPDiscBurningDataType", "-detailLevel", "basic"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return drives

        current_drive = None
        in_media_section = False  # Track if we're parsing Media: child lines

        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("Disc Burning"):
                continue

            # Check for deeper indentation (child lines)
            # system_profiler uses 6 spaces for properties and 10+ spaces for child properties
            if line.startswith("          ") or line.startswith("\t\t"):
                # This is a child line of the previous parent
                if in_media_section and current_drive:
                    # If we see any child line under Media:, a disc is present
                    current_drive["has_disc"] = True
                continue

            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            # Drive name headers have 4 spaces indentation
            is_drive_header = line.startswith("    ") and not line.startswith("      ")

            if value:
                # Key: Value line — update current drive attributes
                if key == "Interconnect" and current_drive:
                    current_drive["drive_type"] = value.lower()
                elif key == "Media" and current_drive:
                    # Old logic: current_drive["has_disc"] = value.lower() != "no"
                    # New logic: We'll detect media in child lines instead
                    pass  # Handled by child line detection above
            elif stripped.endswith(":") and not value:
                if is_drive_header:
                    # This is a drive name header line (e.g., "HL-DT-ST DVDRAM GP65NB60:")
                    if current_drive:
                        drives.append(current_drive)
                    current_drive = {
                        "device": "",
                        "name": key,
                        "has_disc": False,
                        "drive_type": "unknown",
                    }
                    in_media_section = False
                elif key == "Media":
                    # Mark that we're entering a Media section (property, not drive header)
                    in_media_section = True

        if current_drive:
            drives.append(current_drive)

        # Try to find the device path via diskutil
        _resolve_macos_device_paths(drives)

    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.exception("Failed to detect drives on macOS")

    return drives


def _resolve_macos_device_paths(drives: list[dict]) -> None:
    """Try to resolve /dev/diskN paths for detected optical drives."""
    optical_device = None
    try:
        result = subprocess.run(
            ["diskutil", "list"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            # Look for lines like "/dev/disk2 (external, physical):"
            if line.startswith("/dev/disk") and "external" in line:
                device = line.split()[0].rstrip(":")
                # Convert to raw device (rdisk) for better CD reading compatibility
                raw_device = device.replace("/dev/disk", "/dev/rdisk")
                # Check next few lines for CD_partition_scheme to confirm it's optical
                optical_device = raw_device
            elif optical_device and "CD_partition_scheme" in line:
                # This is definitely an optical drive
                for drive in drives:
                    if not drive["device"]:
                        drive["device"] = optical_device
                        break
                optical_device = None  # Reset for next drive
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # If no device path could be resolved, leave device as "" so the
    # caller knows to prompt the user for manual configuration.


def _detect_drives_linux() -> list[dict]:
    """Detect optical drives on Linux by scanning /sys/block and /dev."""
    drives = []

    # Check /sys/block for sr* devices (SCSI CD-ROM)
    sys_block = Path("/sys/block")
    if sys_block.exists():
        for entry in sorted(sys_block.iterdir()):
            if entry.name.startswith("sr"):
                device = f"/dev/{entry.name}"
                name = _read_sysfs_attr(entry / "device" / "model", entry.name)
                drive_type = _read_sysfs_attr(entry / "device" / "transport", "unknown")
                has_disc = _check_disc_linux(device)

                drives.append({
                    "device": device,
                    "name": name.strip(),
                    "has_disc": has_disc,
                    "drive_type": drive_type.strip(),
                })

    # Fallback: check if /dev/cdrom symlink exists
    if not drives:
        cdrom = Path("/dev/cdrom")
        if cdrom.exists():
            drives.append({
                "device": str(cdrom.resolve()),
                "name": "CD-ROM Drive",
                "has_disc": _check_disc_linux(str(cdrom)),
                "drive_type": "unknown",
            })

    return drives


def _read_sysfs_attr(path: Path, default: str = "") -> str:
    """Read a single-line sysfs attribute file."""
    try:
        return path.read_text().strip()
    except (OSError, IOError):
        return default


def _check_disc_linux(device: str) -> bool:
    """Check if a disc is inserted in a Linux device."""
    try:
        result = subprocess.run(
            ["udevadm", "info", "--query=property", f"--name={device}"],
            capture_output=True, text=True, timeout=5
        )
        return "ID_CDROM_MEDIA=1" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
