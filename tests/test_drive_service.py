import subprocess
from unittest.mock import patch, MagicMock

from backend.services.drive_service import (
    _detect_drives_macos,
    _detect_drives_linux,
    _check_disc_linux,
    eject_disc,
)


SAMPLE_SYSTEM_PROFILER_OUTPUT = """Disc Burning:

    HL-DT-ST DVDRAM GP65NB60:

      Firmware Revision: RI06
      Interconnect: USB
      Burn Support: Yes (Apple Shipping Drive)
      Profile Path: Current
      Media:
          Type: CD-ROM
          Blank: No
          Erasable: No
          Overwritable: No
          Appendable: No
"""

SAMPLE_SYSTEM_PROFILER_NO_DISC = """Disc Burning:

    HL-DT-ST DVDRAM GP65NB60:

      Firmware Revision: RI06
      Interconnect: USB
"""


class TestDetectDrivesMacOS:
    @patch("backend.services.drive_service.subprocess.run")
    def test_detects_usb_drive_with_disc(self, mock_run):
        # system_profiler call
        profiler_result = MagicMock()
        profiler_result.returncode = 0
        profiler_result.stdout = SAMPLE_SYSTEM_PROFILER_OUTPUT

        # diskutil call
        diskutil_result = MagicMock()
        diskutil_result.stdout = "/dev/disk2 (external, physical, optical):\n"

        mock_run.side_effect = [profiler_result, diskutil_result]

        drives = _detect_drives_macos()
        assert len(drives) == 1
        assert drives[0]["name"] == "HL-DT-ST DVDRAM GP65NB60"
        assert drives[0]["has_disc"] is True
        assert drives[0]["drive_type"] == "usb"

    @patch("backend.services.drive_service.subprocess.run")
    def test_detects_drive_without_disc(self, mock_run):
        profiler_result = MagicMock()
        profiler_result.returncode = 0
        profiler_result.stdout = SAMPLE_SYSTEM_PROFILER_NO_DISC

        diskutil_result = MagicMock()
        diskutil_result.stdout = ""

        mock_run.side_effect = [profiler_result, diskutil_result]

        drives = _detect_drives_macos()
        assert len(drives) == 1
        assert drives[0]["has_disc"] is False

    @patch("backend.services.drive_service.subprocess.run")
    def test_returns_empty_on_failure(self, mock_run):
        mock_run.side_effect = FileNotFoundError("not found")
        drives = _detect_drives_macos()
        assert drives == []


class TestDetectDrivesLinux:
    @patch("backend.services.drive_service._check_disc_linux", return_value=True)
    @patch("backend.services.drive_service.Path")
    def test_detects_sr_devices(self, mock_path_cls, _mock_check):
        # Build sr0 mock with a realistic / operator chain:
        # sr0 / "device" -> device_mock
        # device_mock / "model" -> model_mock  (read_text returns model string)
        # device_mock / "transport" -> transport_mock  (read_text returns transport string)
        model_mock = MagicMock()
        model_mock.read_text.return_value = "DVDRAM GP65NB60\n"
        transport_mock = MagicMock()
        transport_mock.read_text.return_value = "usb\n"

        sysfs_attrs = {
            "model": model_mock,
            "transport": transport_mock,
        }
        device_mock = MagicMock()
        device_mock.__truediv__ = MagicMock(
            side_effect=lambda k: sysfs_attrs.get(k, MagicMock(read_text=MagicMock(side_effect=OSError)))
        )

        sr0 = MagicMock()
        sr0.name = "sr0"
        sr0.__truediv__ = MagicMock(return_value=device_mock)

        sys_block = MagicMock()
        sys_block.exists.return_value = True
        sys_block.iterdir.return_value = [sr0]

        def path_factory(p):
            if p == "/sys/block":
                return sys_block
            return MagicMock(exists=MagicMock(return_value=False))

        mock_path_cls.side_effect = path_factory

        drives = _detect_drives_linux()
        assert len(drives) == 1
        assert drives[0]["device"] == "/dev/sr0"


class TestCheckDiscLinux:
    @patch("backend.services.drive_service.subprocess.run")
    def test_disc_present(self, mock_run):
        result = MagicMock()
        result.stdout = "ID_CDROM=1\nID_CDROM_MEDIA=1\n"
        mock_run.return_value = result
        assert _check_disc_linux("/dev/sr0") is True

    @patch("backend.services.drive_service.subprocess.run")
    def test_no_disc(self, mock_run):
        result = MagicMock()
        result.stdout = "ID_CDROM=1\n"
        mock_run.return_value = result
        assert _check_disc_linux("/dev/sr0") is False


class TestEjectDisc:
    @patch("backend.services.drive_service.sys")
    @patch("backend.services.drive_service.subprocess.run")
    def test_eject_macos(self, mock_run, mock_sys):
        mock_sys.platform = "darwin"
        mock_run.return_value = MagicMock(returncode=0)
        # eject_disc checks sys.platform at the module level, not via mock
        # So we test the subprocess call directly
        assert eject_disc("/dev/disk2") is True

    @patch("backend.services.drive_service.subprocess.run")
    def test_eject_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "eject")
        assert eject_disc("/dev/sr0") is False
