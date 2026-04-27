import logging
import musicbrainzngs

logger = logging.getLogger(__name__)

# Configure the musicbrainzngs client
musicbrainzngs.set_useragent("SoundBrainz", "0.1.0", "soundbrainz@example.com")
musicbrainzngs.set_rate_limit()

# Includes to request when looking up releases by disc ID
_RELEASE_INCLUDES = ["recordings", "artists", "release-groups"]


def get_disc_id(device: str) -> dict:
    """Read disc ID and detailed TOC information from a CD device using libdiscid.

    Returns:
        Dict with keys: disc_id, toc, total_tracks, track_details
    """
    try:
        import discid
        disc = discid.read(device)

        # Extract detailed track information from TOC
        track_details = []
        for i, track in enumerate(disc.tracks, start=1):
            duration_ms = int((track.length / 75) * 1000) if track.length else 0

            track_details.append({
                "number": i,
                "duration_ms": duration_ms,
                "offset": track.offset,
                "title": f"Track {i:02d}",  # Generic title for physical disc
            })

        return {
            "disc_id": disc.id,
            "toc": disc.toc_string,
            "total_tracks": len(disc.tracks),
            "track_details": track_details,
        }
    except ImportError:
        raise RuntimeError("discid library not installed. Install with: pip install discid (requires libdiscid)")
    except Exception as e:
        raise RuntimeError(f"Failed to read disc ID from {device}: {e}")


def generate_fallback_metadata(device: str, disc_info: dict, disc_number: int = 1, total_discs: int = 1) -> dict:
    """Generate fallback metadata from physical disc when MusicBrainz lookup fails.

    Args:
        device: CD device path
        disc_info: Dict with disc_id, toc, total_tracks from get_disc_id()
        disc_number: Disc position in multi-disc set (default: 1)
        total_discs: Total number of discs in set (default: 1)

    Returns:
        Dict with basic release info using track count and durations from TOC
    """
    import discid

    # Re-read the disc to get detailed track information
    disc = discid.read(device)

    # Extract track durations from TOC
    tracks = []
    for i, track in enumerate(disc.tracks, start=1):
        # Calculate duration in milliseconds (sectors / 75 * 1000)
        duration_ms = int((track.length / 75) * 1000) if track.length else 0

        # Format duration as MM:SS
        minutes = duration_ms // 60000
        seconds = (duration_ms % 60000) // 1000

        tracks.append({
            "number": i,
            "title": f"Track {i:02d}",  # Generic title
            "duration_ms": duration_ms,
            "artist": "Unknown Artist",
        })

    return {
        "mbid": "",  # No MusicBrainz ID
        "artist": "Unknown Artist",
        "album": f"Unknown Disc ({disc_info['disc_id'][:8]})",
        "year": "",
        "country": "",
        "label": "",
        "language": "",
        "release_type": "",
        "medium_format": "CD",
        "disc_number": 1,
        "total_discs": 1,
        "tracks": tracks,
        "cover_art_url": "",
        "priority_score": -1,  # Lowest priority
        "match_reasons": ["Fallback metadata from physical disc"],
    }


def lookup_disc(disc_id: str, toc: str | None = None, physical_track_details: list = None) -> list[dict]:
    """Look up a disc on MusicBrainz by disc ID.

    Falls back to TOC-based fuzzy lookup if exact match fails.

    Args:
        disc_id: Physical disc ID
        toc: Table of Contents string for fuzzy matching
        physical_track_details: Detailed track info from physical disc TOC

    Returns:
        List of formatted release dicts.
    """
    releases = []

    try:
        # Exact disc ID lookup
        result = musicbrainzngs.get_releases_by_discid(
            disc_id, includes=_RELEASE_INCLUDES
        )

        if "disc" in result:
            raw_releases = result["disc"].get("release-list", [])
            releases = [format_release(r, disc_id, physical_track_details) for r in raw_releases]

        elif "release-list" in result:
            # Direct release list (CD stub)
            releases = [format_release(r, disc_id, physical_track_details) for r in result["release-list"]]

    except musicbrainzngs.ResponseError as e:
        logger.info("Exact disc ID lookup returned no results (disc not in MusicBrainz database), trying TOC-based fallback")

    # Fallback: TOC-based fuzzy lookup
    if not releases and toc:
        try:
            result = musicbrainzngs.get_releases_by_discid(
                disc_id, toc=toc, includes=_RELEASE_INCLUDES, cdstubs=False
            )
            if "release-list" in result:
                releases = [format_release(r, disc_id, physical_track_details) for r in result["release-list"]]
                logger.info("TOC-based lookup found %d release(s)", len(releases))
        except musicbrainzngs.ResponseError as e:
            logger.warning("Both exact and TOC-based lookups failed. Disc may not be in MusicBrainz: %s", e)

    return releases


def _prioritize_releases(releases: list[dict], user_preferences: dict) -> list[dict]:
    """Sort releases by smart scoring algorithm.

    Scoring factors:
    - CD format vs digital: +100 points for CD
    - Language match: +50 points for primary language, +25 for secondary
    - Country match: +20 points
    - Original position: +1 point (to maintain relative order for ties)

    Args:
        releases: List of formatted release dicts
        user_preferences: User config dict with preferred_languages and preferred_country

    Returns:
        Sorted list of releases with highest score first
    """
    def score_release(release: dict) -> tuple[int, list[str]]:
        """Calculate score and return (score, reasons)."""
        score = 0
        reasons = []

        # Medium format priority (CD > Digital)
        if release.get("medium_format") == "CD":
            score += 100
            reasons.append("CD format")
        elif release.get("medium_format") == "Digital Media":
            reasons.append("Digital format")

        # Language matching (priority order)
        release_language = release.get("language", "")
        preferred_languages = user_preferences.get("preferred_languages", ["en"])

        for i, lang in enumerate(preferred_languages):
            if release_language == lang:
                if i == 0:  # Primary language
                    score += 50
                    reasons.append(f"Primary language match: {lang}")
                else:  # Secondary language
                    score += 25
                    reasons.append(f"Language match: {lang}")
                break

        # Country matching
        preferred_country = user_preferences.get("preferred_country", "")
        if preferred_country and release.get("country") == preferred_country:
            score += 20
            reasons.append(f"Country match: {preferred_country}")

        return score, reasons

    # Score all releases
    scored_releases = []
    for i, release in enumerate(releases):
        score, reasons = score_release(release)
        release["priority_score"] = score
        release["match_reasons"] = reasons
        release["original_position"] = i
        scored_releases.append((score, i, release))

    # Sort by score (descending), then by original position
    scored_releases.sort(key=lambda x: (-x[0], x[1]))

    # Return sorted releases
    return [release for _, _, release in scored_releases]


def format_release(release: dict, disc_id: str, physical_track_details: list = None) -> dict:
    """Normalize a MusicBrainz release dict into a clean format.

    Args:
        release: MusicBrainz release dict
        disc_id: Physical disc ID
        physical_track_details: Detailed track info from physical disc TOC

    Returns:
        Dict with: mbid, artist, album, year, country, label, language, tracks, cover_art_url, disc_number, total_discs
    """
    mbid = release.get("id", "")

    # Artist credit
    artist_credit_list = release.get("artist-credit")
    if not artist_credit_list:
        logger.debug("Release %s has no artist-credit or it's None/empty", mbid)
    artist = _extract_artist_credit(artist_credit_list or [])

    # Album title
    album = release.get("title", "Unknown Album")
    if not album or album.strip() == "":
        logger.debug("Release %s has empty album title, using 'Unknown Album'", mbid)
        album = "Unknown Album"

    # Year from date
    date = release.get("date", "")
    year = date[:4] if date else ""

    # Country
    country = release.get("country", "")

    # Label
    label = ""
    label_info = release.get("label-info-list", [])
    if label_info and "label" in label_info[0]:
        label = label_info[0]["label"].get("name", "")

    # Language
    language = release.get("text-representation", {}).get("language", "")

    # Release group type
    release_group = release.get("release-group", {})
    release_type = release_group.get("type", "")

    # NEW: Extract medium format
    medium_list = release.get("medium-list", [])
    medium_format = medium_list[0].get("format", "Unknown") if medium_list else "Unknown"

    # Tracks with disc information
    tracks, disc_number, total_discs = _extract_tracks(release, disc_id, physical_track_details)

    # Cover art URL (from Cover Art Archive)
    cover_art_url = f"https://coverartarchive.org/release/{mbid}/front-500" if mbid else ""

    # Log the extracted release data for debugging
    logger.debug("format_release for %s: artist='%s', album='%s', tracks=%d, disc_number=%s, total_discs=%d",
                 mbid, artist, album, len(tracks), disc_number, total_discs)

    return {
        "mbid": mbid,
        "artist": artist,
        "album": album,
        "year": year,
        "country": country,
        "label": label,
        "language": language,
        "release_type": release_type,
        "medium_format": medium_format,
        "disc_number": disc_number if disc_number else 1,  # Default to 1 if None
        "total_discs": total_discs,
        "tracks": tracks,
        "cover_art_url": cover_art_url,
    }


def _calculate_track_similarity(physical_tracks: list, medium_tracks: list) -> float:
    """Calculate similarity score between physical disc tracks and medium tracks.

    Compares track durations and titles to determine likelihood of match.
    Returns a score between 0.0 (no match) and 1.0 (perfect match).

    Args:
        physical_tracks: List of track info from physical disc (from TOC)
        medium_tracks: List of track info from MusicBrainz medium

    Returns:
        Similarity score as float
    """
    if not physical_tracks or not medium_tracks:
        return 0.0

    if len(physical_tracks) != len(medium_tracks):
        return 0.0  # Different track counts = no match

    # Calculate similarity based on duration and title matching
    total_similarity = 0.0

    for phys_track, med_track in zip(physical_tracks, medium_tracks):
        # Duration matching (within 5 seconds = good match)
        phys_duration = phys_track.get("duration_ms", 0)
        med_duration = med_track.get("duration_ms", 0)

        if phys_duration and med_duration:
            duration_diff = abs(phys_duration - med_duration)
            # Allow 5 seconds (5000ms) difference for mastering variations
            duration_similarity = max(0, 1.0 - (duration_diff / 5000.0))
        else:
            duration_similarity = 0.5  # Neutral if no duration info

        # Title matching (exact or similar)
        phys_title = phys_track.get("title", "").lower()
        med_title = med_track.get("title", "").lower()

        if phys_title and med_title:
            # Simple similarity based on common words
            phys_words = set(phys_title.split())
            med_words = set(med_title.split())

            if phys_words & med_words:  # Has at least one word in common
                title_similarity = 0.8
            else:
                title_similarity = 0.2
        else:
            title_similarity = 0.5  # Neutral if no title info

        # Combined similarity for this track (70% duration, 30% title)
        track_similarity = (duration_similarity * 0.7) + (title_similarity * 0.3)
        total_similarity += track_similarity

    # Average similarity across all tracks
    return total_similarity / len(physical_tracks)


def _extract_artist_credit(credit_list: list) -> str:
    """Build a combined artist string from MusicBrainz artist-credit list."""
    # Handle None or missing credit_list
    if not credit_list:
        logger.debug("artist-credit is None or empty, returning 'Unknown Artist'")
        return "Unknown Artist"

    parts = []
    for item in credit_list:
        if isinstance(item, dict) and "artist" in item:
            parts.append(item["artist"].get("name", ""))
            # Join phrase (e.g., " & ", " feat. ")
            if "joinphrase" in item:
                parts.append(item["joinphrase"])
        elif isinstance(item, str):
            parts.append(item)
    return "".join(parts) or "Unknown Artist"


def _find_matching_medium(release: dict, disc_id: str) -> dict | None:
    """Find which medium in a release contains the given disc ID."""
    for medium in release.get("medium-list", []):
        for disc in medium.get("disc-list", []):
            if disc.get("id") == disc_id:
                return medium
    return None


def _extract_tracks(release: dict, disc_id: str, physical_track_details: list = None) -> tuple[list[dict], int | None, int]:
    """Extract track listing from a release's media list for a specific disc.

    Args:
        release: MusicBrainz release dict
        disc_id: Physical disc ID from CD
        physical_track_details: Detailed track info from physical disc TOC

    Returns:
        Tuple of (tracks list, disc position or None if uncertain, total discs)
    """
    matching_medium = _find_matching_medium(release, disc_id)

    if not matching_medium:
        # Fallback: try to match by track similarity
        medium_list = release.get("medium-list", [])
        if medium_list and physical_track_details:
            # Find medium with highest track similarity
            best_match = None
            best_similarity = 0.0
            best_tracks = []

            for medium in medium_list:
                medium_tracks = [_extract_track_info(t) for t in medium.get("track-list", [])]
                similarity = _calculate_track_similarity(physical_track_details, medium_tracks)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = medium
                    best_tracks = medium_tracks

            # Use best match if similarity is good enough (> 0.6 = 60% match)
            if best_match and best_similarity > 0.6:
                tracks = best_tracks
                disc_position = int(best_match.get("position", 1))
                total_discs = len(medium_list)
                return tracks, disc_position, total_discs
            else:
                # No good match - use first medium but mark as uncertain
                first_medium = medium_list[0]
                tracks = [_extract_track_info(track) for track in first_medium.get("track-list", [])]
                total_discs = len(medium_list)
                return tracks, None, total_discs  # None indicates uncertain match
        elif medium_list:
            # No physical track details available - use first medium but mark as uncertain
            first_medium = medium_list[0]
            tracks = [_extract_track_info(track) for track in first_medium.get("track-list", [])]
            total_discs = len(medium_list)
            return tracks, None, total_discs
        return [], None, 1

    # Extract only tracks from matching medium
    disc_position = int(matching_medium.get("position", 1))
    total_discs = len(release.get("medium-list", []))

    tracks = []
    for track in matching_medium.get("track-list", []):
        tracks.append(_extract_track_info(track))

    return tracks, disc_position, total_discs


def _extract_track_info(track: dict) -> dict:
    """Extract information from a single track."""
    recording = track.get("recording", {})
    track_artist = _extract_artist_credit(recording.get("artist-credit", []))
    return {
        "number": int(track.get("number", track.get("position", 0))),
        "title": recording.get("title", track.get("title", "Unknown")),
        "duration_ms": int(recording.get("length", 0) or 0),
        "artist": track_artist,
    }