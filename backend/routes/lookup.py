from flask import Blueprint, jsonify, request

from backend.config import load_config
from backend.services.musicbrainz_service import get_disc_id, lookup_disc, _prioritize_releases

lookup_bp = Blueprint("lookup", __name__)


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

    # Look up on MusicBrainz
    releases = lookup_disc(disc_info["disc_id"], toc=disc_info.get("toc"))

    # Apply smart prioritization
    user_preferences = load_config()
    releases = _prioritize_releases(releases, user_preferences)

    return jsonify({
        "disc_id": disc_info["disc_id"],
        "total_tracks": disc_info["total_tracks"],
        "releases": releases,
    })
