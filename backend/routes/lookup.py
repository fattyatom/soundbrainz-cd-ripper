from flask import Blueprint, jsonify, request

from backend.config import load_config
from backend.services.musicbrainz_service import get_disc_id, lookup_disc, _prioritize_releases

lookup_bp = Blueprint("lookup", __name__)

# In-memory tracking for unknown discs during server runtime
_unknown_discs_cache = {}  # disc_id -> (disc_number, total_discs)


def get_disc_number_from_cache(disc_id: str) -> tuple[int, int]:
    """Get disc number based on history of discs with failed ID matching.

    When a new disc is inserted, updates total_discs for ALL previously seen discs.

    Args:
        disc_id: Current disc ID

    Returns:
        Tuple of (disc_number, total_discs)
    """
    if disc_id in _unknown_discs_cache:
        # Returning disc - use its original position
        return _unknown_discs_cache[disc_id]
    else:
        # New disc - increment total count and assign next number
        disc_number = len(_unknown_discs_cache) + 1
        total_discs = len(_unknown_discs_cache) + 1

        # Add to cache
        _unknown_discs_cache[disc_id] = (disc_number, total_discs)

        # Update all previous discs with new total
        for cached_id in _unknown_discs_cache:
            old_disc_num, old_total = _unknown_discs_cache[cached_id]
            _unknown_discs_cache[cached_id] = (old_disc_num, total_discs)

        return disc_number, total_discs


@lookup_bp.route("/api/lookup", methods=["GET"])
def get_lookup():
    """Look up disc metadata on MusicBrainz.

    Query params:
        device: CD drive device path (required)
    """
    device = request.args.get("device")
    if not device:
        return jsonify({"error": "No device specified"}), 400

    try:
        # Read disc ID from the physical disc
        disc_info = get_disc_id(device)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    # Look up on MusicBrainz with track details
    releases = lookup_disc(
        disc_info["disc_id"],
        toc=disc_info.get("toc"),
        physical_track_details=disc_info.get("track_details")
    )

    # Check for releases with uncertain disc matching (original disc_number was None)
    uncertain_matches = [rel for rel in releases if rel.get("disc_number") is None]

    if uncertain_matches:
        # Use cache to assign disc numbers for uncertain matches
        disc_number, total_discs = get_disc_number_from_cache(disc_info["disc_id"])

        # Update uncertain releases with cached disc numbers
        for rel in uncertain_matches:
            rel["disc_number"] = disc_number
            rel["total_discs"] = total_discs
            rel["disc_id_matched"] = False  # Mark for UI indication

        # Mark certain matches
        for rel in releases:
            if rel.get("disc_number") is not None:
                rel["disc_id_matched"] = True
    elif not releases:
        # No releases found - generate fallback metadata from physical disc
        from backend.services.musicbrainz_service import generate_fallback_metadata
        # Get disc number based on cache history
        disc_number, total_discs = get_disc_number_from_cache(disc_info["disc_id"])
        fallback = generate_fallback_metadata(device, disc_info, disc_number, total_discs)
        fallback["disc_id_matched"] = False  # Fallback metadata is always uncertain
        releases = [fallback]
    else:
        # All matches are certain - mark them
        for rel in releases:
            rel["disc_id_matched"] = True

    # Apply smart prioritization only to MusicBrainz releases
    if releases:
        user_preferences = load_config()
        releases = _prioritize_releases(releases, user_preferences)

    return jsonify({
        "disc_id": disc_info["disc_id"],
        "total_tracks": disc_info["total_tracks"],
        "releases": releases,
    })
