from flask import Blueprint, jsonify, request

from backend.services.ripper_service import start_rip, get_status, is_active

rip_bp = Blueprint("rip", __name__)


@rip_bp.route("/api/rip", methods=["POST"])
def post_rip():
    """Start a rip job."""
    if is_active():
        return jsonify({"error": "A rip is already in progress"}), 409

    data = request.get_json(silent=True) or {}
    device = data.get("device")
    if not device:
        return jsonify({"error": "No device specified"}), 400

    release = data.get("release")  # Optional MusicBrainz metadata

    # DEBUG: Log the received release data structure
    import logging
    logger = logging.getLogger(__name__)
    if release:
        logger.info("Received release data from frontend:")
        logger.info(f"  MBID: {release.get('mbid', 'MISSING')}")
        logger.info(f"  Artist: {release.get('artist', 'MISSING')}")
        logger.info(f"  Album: {release.get('album', 'MISSING')}")
        logger.info(f"  Year: {release.get('year', 'MISSING')}")
        logger.info(f"  Disc number: {release.get('disc_number', 'MISSING')}")
        logger.info(f"  Total discs: {release.get('total_discs', 'MISSING')}")
        logger.info(f"  Tracks: {len(release.get('tracks', []))} tracks")

        # Check for missing required fields
        required_fields = ['artist', 'album', 'tracks']
        missing_fields = [field for field in required_fields if not release.get(field)]
        if missing_fields:
            logger.warning(f"Release data missing required fields: {missing_fields}")
            logger.warning(f"Complete release data: {release}")
    else:
        logger.info("No release data received - will rip without metadata")

    output_dir = data.get("output_dir")
    selected_tracks = data.get("selectedTracks")  # Optional list of track numbers to rip

    # If no output_dir specified, use the configured default
    if not output_dir:
        from backend.config import load_config
        config = load_config()
        output_dir = config.get("output_dir")

    status = start_rip(device, release=release, output_dir=output_dir, selected_tracks=selected_tracks)
    return jsonify(status)


@rip_bp.route("/api/rip/status", methods=["GET"])
def get_rip_status():
    """Return current rip progress."""
    return jsonify(get_status())
