import pytest
from backend.config import migrate_config, DEFAULTS


class TestConfigMigration:
    """Test configuration migration logic."""

    def test_migrates_exact_default_single_disc_pattern(self):
        """Exact old default pattern should migrate to new default."""
        old_pattern = "{artist}/{album}/{number:02d} - {title}.{ext}"
        config = {"folder_pattern": old_pattern}
        migrated = migrate_config(config)
        assert migrated["folder_pattern"] == "{album_artist}/{album}/{number:02d} - {title}.{ext}"

    def test_migrates_exact_default_multi_disc_pattern(self):
        """Exact old default multi-disc pattern should migrate."""
        old_pattern = "{artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}"
        config = {"folder_pattern_multi_disc": old_pattern}
        migrated = migrate_config(config)
        assert migrated["folder_pattern_multi_disc"] == "{album_artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}"

    def test_migrates_simple_custom_patterns(self):
        """Simple patterns starting with {artist}/ should migrate."""
        config = {"folder_pattern": "{artist}/{album}/{title}.{ext}"}
        migrated = migrate_config(config)
        assert migrated["folder_pattern"] == "{album_artist}/{album}/{title}.{ext}"

    def test_preserves_complex_patterns(self):
        """Complex patterns should not be migrated."""
        config = {"folder_pattern": "{album}/{artist} - {title}.{ext}"}
        migrated = migrate_config(config)
        assert migrated["folder_pattern"] == "{album}/{artist} - {title}.{ext}"  # Unchanged

    def test_preserves_multiple_artist_occurrences(self):
        """Patterns with multiple {artist} should not be migrated."""
        config = {"folder_pattern": "{artist}/{album}/{artist} - {title}.{ext}"}
        migrated = migrate_config(config)
        assert migrated["folder_pattern"] == "{artist}/{album}/{artist} - {title}.{ext}"  # Unchanged

    def test_new_installations_get_album_artist_defaults(self):
        """Fresh installs should use {album_artist} in defaults."""
        assert DEFAULTS["folder_pattern"] == "{album_artist}/{album}/{number:02d} - {title}.{ext}"
        assert DEFAULTS["folder_pattern_multi_disc"] == "{album_artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}"

    def test_preserves_already_migrated_patterns(self):
        """Patterns already using {album_artist} should not be changed."""
        config = {"folder_pattern": "{album_artist}/{album}/{number:02d} - {title}.{ext}"}
        migrated = migrate_config(config)
        assert migrated["folder_pattern"] == "{album_artist}/{album}/{number:02d} - {title}.{ext}"  # Unchanged

    def test_migrates_both_patterns_simultaneously(self):
        """Both single and multi-disc patterns should migrate together."""
        config = {
            "folder_pattern": "{artist}/{album}/{number:02d} - {title}.{ext}",
            "folder_pattern_multi_disc": "{artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}"
        }
        migrated = migrate_config(config)
        assert migrated["folder_pattern"] == "{album_artist}/{album}/{number:02d} - {title}.{ext}"
        assert migrated["folder_pattern_multi_disc"] == "{album_artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}"

    def test_handles_missing_pattern_gracefully(self):
        """Missing patterns should use defaults."""
        config = {}
        migrated = migrate_config(config)
        assert "folder_pattern" in migrated
        assert "folder_pattern_multi_disc" in migrated
        assert migrated["folder_pattern"] == DEFAULTS["folder_pattern"]
        assert migrated["folder_pattern_multi_disc"] == DEFAULTS["folder_pattern_multi_disc"]