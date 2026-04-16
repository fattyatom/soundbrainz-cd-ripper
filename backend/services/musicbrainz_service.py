import logging
import musicbrainzngs

logger = logging.getLogger(__name__)

# Configure the musicbrainzngs client
musicbrainzngs.set_useragent("SoundBrainz", "0.1.0", "soundbrainz@example.com")
musicbrainzngs.set_rate_limit()

# Includes to request when looking up releases by disc ID
_RELEASE_INCLUDES = ["recordings", "artists", "release-groups", "labels", "media"]


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
            releases = [format_release(r) for r in raw_releases]

        elif "release-list" in result:
            # Direct release list (CD stub)
            releases = [format_release(r) for r in result["release-list"]]

    except musicbrainzngs.ResponseError as e:
        logger.warning("Exact disc lookup failed: %s", e)

    # Fallback: TOC-based fuzzy lookup
    if not releases and toc:
        try:
            result = musicbrainzngs.get_releases_by_discid(
                disc_id, toc=toc, includes=_RELEASE_INCLUDES, cdstubs=False
            )
            if "release-list" in result:
                releases = [format_release(r) for r in result["release-list"]]
        except musicbrainzngs.ResponseError as e:
            logger.warning("TOC-based lookup also failed: %s", e)

    return releases


def format_release(release: dict) -> dict:
    """Normalize a MusicBrainz release dict into a clean format.

    Returns:
        Dict with: mbid, artist, album, year, country, label, language, tracks, cover_art_url
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

    # Tracks
    tracks = _extract_tracks(release)

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


def _extract_tracks(release: dict) -> list[dict]:
    """Extract track listing from a release's media list."""
    tracks = []
    for medium in release.get("medium-list", []):
        for track in medium.get("track-list", []):
            recording = track.get("recording", {})
            track_artist = _extract_artist_credit(recording.get("artist-credit", []))
            tracks.append({
                "number": int(track.get("number", track.get("position", 0))),
                "title": recording.get("title", track.get("title", "Unknown")),
                "duration_ms": int(recording.get("length", 0) or 0),
                "artist": track_artist,
            })
    return tracks