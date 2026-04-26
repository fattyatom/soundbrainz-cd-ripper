"""Test threading improvements in ripper_service.py"""
import threading
import time
from unittest.mock import patch, MagicMock
import pytest
from backend.services.ripper_service import rip_state, _rip_lock, get_status, is_active, start_rip


@pytest.fixture(autouse=True)
def reset_rip_state():
    """Reset rip state before each test."""
    with _rip_lock:
        rip_state.clear()
        rip_state.update({
            "active": False,
            "phase": "idle",
            "track": 0,
            "total_tracks": 0,
            "percent": 0,
            "error": None,
            "output_dir": None,
        })
    yield
    # Cleanup after test
    with _rip_lock:
        rip_state.clear()
        rip_state.update({
            "active": False,
            "phase": "idle",
            "track": 0,
            "total_tracks": 0,
            "percent": 0,
            "error": None,
            "output_dir": None,
        })


class TestThreadSafety:
    """Test that rip_state access is thread-safe."""

    def test_get_status_returns_copy(self):
        """Test that get_status() returns a copy, not the original dict."""
        # Set some state
        with _rip_lock:
            rip_state.update({
                "active": True,
                "phase": "ripping",
                "track": 1,
                "total_tracks": 10,
                "percent": 50,
            })

        # Get status
        status = get_status()

        # Modify the returned dict
        status["percent"] = 999

        # Original should be unchanged
        with _rip_lock:
            assert rip_state["percent"] == 50

    def test_concurrent_status_access(self):
        """Test that multiple threads can safely access status."""
        results = []
        errors = []

        def access_status():
            try:
                for _ in range(100):
                    status = get_status()
                    results.append(status)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=access_status)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0
        assert len(results) == 1000  # 10 threads * 100 accesses

    def test_is_active_thread_safety(self):
        """Test that is_active() is thread-safe."""
        results = []
        errors = []

        def check_active():
            try:
                for _ in range(50):
                    active = is_active()
                    results.append(active)
            except Exception as e:
                errors.append(e)

        # Start threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=check_active)
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0


class TestDependencyChecking:
    """Test the new dependency checking functionality."""

    @patch('backend.services.ripper_service.subprocess.run')
    @patch('backend.services.ripper_service._find_cdparanoia')
    def test_check_dependencies_success(self, mock_cdparanoia, mock_run):
        """Test successful dependency check."""
        from backend.services.ripper_service import _check_dependencies

        mock_cdparanoia.return_value = "cd-paranoia"
        mock_run.return_value = MagicMock(returncode=0)

        # Should not raise
        _check_dependencies()

    @patch('backend.services.ripper_service.shutil.which')
    def test_check_dependencies_missing_cdparanoia(self, mock_which):
        """Test dependency check when cdparanoia is missing."""
        from backend.services.ripper_service import _check_dependencies

        mock_which.return_value = None  # No tools found

        with pytest.raises(RuntimeError) as exc_info:
            _check_dependencies()

        # The function should call _find_cdparanoia() which throws the error
        assert "CD ripping tool" in str(exc_info.value) or "Missing dependencies" in str(exc_info.value)

    @patch('backend.services.ripper_service.subprocess.run')
    @patch('backend.services.ripper_service.shutil.which')
    @patch('backend.services.ripper_service._find_cdparanoia')
    def test_check_dependencies_missing_ffmpeg(self, mock_cdparanoia, mock_which, mock_run):
        """Test dependency check when ffmpeg is missing."""
        from backend.services.ripper_service import _check_dependencies

        # cdparanoia exists and works
        mock_cdparanoia.return_value = "cd-paranoia"

        def which_func(cmd):
            # cdparanoia exists, ffmpeg doesn't
            return "cd-paranoia" if cmd in ["cd-paranoia", "cdparanoia"] else None

        mock_which.side_effect = which_func

        # First call (cdparanoia) succeeds, second (ffmpeg) fails
        mock_run.side_effect = [
            MagicMock(returncode=0),  # cdparanoia works
            MagicMock(returncode=1)   # ffmpeg fails
        ]

        with pytest.raises(RuntimeError) as exc_info:
            _check_dependencies()

        # The function should detect ffmpeg issue
        error_msg = str(exc_info.value).lower()
        assert "ffmpeg" in error_msg or "missing dependencies" in error_msg


class TestThreadManagement:
    """Test improved thread management."""

    @patch('backend.services.ripper_service.threading.Thread')
    def test_start_rip_returns_status(self, mock_thread):
        """Test that start_rip returns proper status dict."""
        # Mock the thread to not actually start
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        status = start_rip("/dev/sr0", {"album": "Test"}, "/tmp/music")

        assert isinstance(status, dict)
        # Should have updated status (no error)
        assert status.get("error") is None
        # Phase should be "starting" initially
        assert status.get("phase") == "starting"
        # Should be marked as active
        assert status.get("active") == True

    @patch('backend.services.ripper_service.threading.Thread')
    def test_start_rip_prevents_duplicate_rips(self, mock_thread):
        """Test that duplicate rip attempts are prevented."""
        # Mock the thread to not actually start
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # First rip should succeed
        status1 = start_rip("/dev/sr0", {"album": "Test"}, "/tmp/music")
        assert status1.get("error") is None
        assert status1.get("active") == True

        # Second rip should fail
        status2 = start_rip("/dev/sr1", {"album": "Test2"}, "/tmp/music")
        assert status2.get("error") is not None
        assert "already in progress" in status2["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])