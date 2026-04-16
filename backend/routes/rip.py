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
    output_dir = data.get("output_dir")

    status = start_rip(device, release=release, output_dir=output_dir)
    return jsonify(status)


@rip_bp.route("/api/rip/status", methods=["GET"])
def get_rip_status():
    """Return current rip progress."""
    return jsonify(get_status())
