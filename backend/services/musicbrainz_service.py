import logging
import musicbrainzngs

logger = logging.getLogger(__name__)

# Configure the musicbrainzngs client
musicbrainzngs.set_useragent("SoundBrainz", "0.1.0", "soundbrainz@example.com")
musicbrainzngs.set_rate_limit()

# Includes to request when looking up releases by disc ID
_RELEASE_INCLUDES = ["recordings", "artists", "release-groups"]


def get_disc_id(device: str) -> dict:
    """Read disc ID and TOC from a CD device using libdiscid.

    Returns:
        Dict with keys: disc_id, toc, total_tracks
    """
    try:
        import discid
        disc = discid.read(device)
        return {
            "disc_id": disc.id,
            "toc": disc.toc_string,
            "total_tracks": len(disc.tracks),
        }
    except ImportError:
        raise RuntimeError("discid library not installed. Install with: pip install discid (requires libdiscid)")
    except Exception as e:
        raise RuntimeError(f"Failed to read disc ID from {device}: {e}")


def generate_fallback_metadata(device: str, disc_info: dict) -> dict:
    """Generate fallback metadata from physical disc when MusicBrainz lookup fails.

    Args:
        device: CD device path
        disc_info: Dict with disc_id, toc, total_tracks from get_disc_id()

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


def lookup_disc(disc_id: str, toc: str | None = None) -> list[dict]:
    """Look up a disc on MusicBrainz by disc ID.

    Falls back to TOC-based fuzzy lookup if exact match fails.

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
            releases = [format_release(r, disc_id) for r in raw_releases]

        elif "release-list" in result:
            # Direct release list (CD stub)
            releases = [format_release(r, disc_id) for r in result["release-list"]]

    except musicbrainzngs.ResponseError as e:
        logger.warning("Exact disc lookup failed: %s", e)

    # Fallback: TOC-based fuzzy lookup
    if not releases and toc:
        try:
            result = musicbrainzngs.get_releases_by_discid(
                disc_id, toc=toc, includes=_RELEASE_INCLUDES, cdstubs=False
            )
            if "release-list" in result:
                releases = [format_release(r, disc_id) for r in result["release-list"]]
        except musicbrainzngs.ResponseError as e:
            logger.warning("TOC-based lookup also failed: %s", e)

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


def format_release(release: dict, disc_id: str) -> dict:
    """Normalize a MusicBrainz release dict into a clean format.

    Returns:
        Dict with: mbid, artist, album, year, country, label, language, tracks, cover_art_url, disc_number, total_discs
    """
    mbid = release.get("id", "")

    # Artist credit
    artist = _extract_artist_credit(release.get("artist-credit", []))

    # Album title
    album = release.get("title", "Unknown Album")

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
    tracks, disc_number, total_discs = _extract_tracks(release, disc_id)

    # Cover art URL (from Cover Art Archive)
    cover_art_url = f"https://coverartarchive.org/release/{mbid}/front-500" if mbid else ""

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
        "disc_number": disc_number,
        "total_discs": total_discs,
        "tracks": tracks,
        "cover_art_url": cover_art_url,
    }


def _extract_artist_credit(credit_list: list) -> str:
    """Build a combined artist string from MusicBrainz artist-credit list."""
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


def _extract_tracks(release: dict, disc_id: str) -> tuple[list[dict], int, int]:
    """Extract track listing from a release's media list for a specific disc.

    Returns:
        Tuple of (tracks list, disc position, total discs)
    """
    matching_medium = _find_matching_medium(release, disc_id)

    if not matching_medium:
        # Fallback: extract tracks from first medium only
        # This prevents combining tracks from all discs when disc ID matching fails
        medium_list = release.get("medium-list", [])
        if medium_list:
            first_medium = medium_list[0]
            tracks = [_extract_track_info(track) for track in first_medium.get("track-list", [])]
            total_discs = len(medium_list)
            return tracks, 1, total_discs
        return [], 1, 1

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