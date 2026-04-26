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

    def test_generate_path_with_album_artist(self):
        """Test that {album_artist} placeholder works in patterns."""
        metadata = {
            "album_artist": "Hans Zimmer",
            "artist": "Hans Zimmer & Lisa Gerrard",
            "album": "Gladiator",
            "title": "Now We Are Free",
            "number": 15,
            "ext": "flac"
        }

        pattern = "{album_artist}/{album}/{number:02d} - {title}.{ext}"
        result = generate_path("/Music", pattern, metadata)

        assert result == "/Music/Hans Zimmer/Gladiator/15 - Now We Are Free.flac"

    def test_various_artists_album_organization(self):
        """Test that various artists albums group correctly."""
        metadata = {
            "album_artist": "Various Artists",
            "artist": "Queen",
            "album": "Highlander Soundtrack",
            "title": "Princes of the Universe",
            "number": 1,
            "ext": "flac"
        }

        pattern = "{album_artist}/{album}/{number:02d} - {title}.{ext}"
        result = generate_path("/Music", pattern, metadata)

        # Should group under "Various Artists", not "Queen"
        assert result == "/Music/Various Artists/Highlander Soundtrack/01 - Princes of the Universe.flac"

    def test_album_artist_with_multi_disc(self):
        """Test album artist with multi-disc albums."""
        metadata = {
            "album_artist": "Pink Floyd",
            "artist": "Pink Floyd",
            "album": "The Wall",
            "title": "Another Brick in the Wall",
            "number": 1,
            "disc": 1,
            "total_discs": 2,
            "ext": "flac"
        }

        pattern = "{album_artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}"
        result = generate_path("/Music", pattern, metadata)

        assert result == "/Music/Pink Floyd/The Wall/CD1/01 - Another Brick in the Wall.flac"
