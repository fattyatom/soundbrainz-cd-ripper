import pytest
from backend.services.library_service import generate_path


class TestGeneratePath:
    """Test the generate_path function with various patterns."""

    def test_single_disc_pattern(self):
        """Test single-disc file naming pattern."""
        metadata = {
            "artist": "Test Artist",
            "album": "Test Album",
            "title": "Test Track",
            "number": 1,
        }
        result = generate_path("/Music", "{artist}/{album}/{number:02d} - {title}.flac", metadata)
        assert result == "/Music/Test Artist/Test Album/01 - Test Track.flac"

    def test_multi_disc_pattern(self):
        """Test multi-disc file naming pattern with CD{disc}."""
        metadata = {
            "artist": "Test Artist",
            "album": "Test Album",
            "title": "Test Track",
            "number": 1,
            "disc": 2,
            "total_discs": 2,
        }
        result = generate_path("/Music", "{artist}/{album}/CD{disc}/{number:02d} - {title}.flac", metadata)
        assert result == "/Music/Test Artist/Test Album/CD2/01 - Test Track.flac"

    def test_multi_disc_first_disc(self):
        """Test multi-disc pattern for first disc."""
        metadata = {
            "artist": "Test Artist",
            "album": "Test Album",
            "title": "Test Track",
            "number": 5,
            "disc": 1,
            "total_discs": 3,
        }
        result = generate_path("/Music", "{artist}/{album}/CD{disc}/{number:02d} - {title}.flac", metadata)
        assert result == "/Music/Test Artist/Test Album/CD1/05 - Test Track.flac"

    def test_fallback_on_pattern_error(self):
        """Test fallback pattern when the pattern fails."""
        metadata = {
            "artist": "Test Artist",
            "album": "Test Album",
            "title": "Test Track",
            "number": 1,
        }
        # Use an invalid pattern with missing keys
        result = generate_path("/Music", "{artist}/{invalid}/{title}.flac", metadata)
        # Should fall back to default pattern
        assert "Test Artist" in result
        assert "Test Album" in result
        assert "Test Track" in result
        assert ".flac" in result

    def test_sanitization_of_special_chars(self):
        """Test that special characters in filenames are sanitized."""
        metadata = {
            "artist": "Test/Artist",
            "album": "Album:Name",
            "title": "Track<Name>",
            "number": 1,
        }
        result = generate_path("/Music", "{artist}/{album}/{number:02d} - {title}.flac", metadata)
        # Special characters should be replaced with underscores
        assert "Test_Artist" in result
        assert "Album_Name" in result
        assert "Track_Name_" in result
        # Check that we have proper path structure
        parts = result.split("/")
        assert parts[0] == ""  # Empty before first /
        assert parts[1] == "Music"
        assert parts[2] == "Test_Artist"
        assert parts[3] == "Album_Name"
        assert "01 - Track_Name_.flac" == parts[4]
