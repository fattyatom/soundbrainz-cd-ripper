from flask import Blueprint, jsonify

from backend.services.drive_service import detect_drives, eject_disc

drives_bp = Blueprint("drives", __name__)


@drives_bp.route("/api/drives", methods=["GET"])
def get_drives():
    """Return list of detected CD/DVD drives."""
    drives = detect_drives()
    return jsonify({"drives": drives})


@drives_bp.route("/api/drives/eject", methods=["POST"])
def post_eject():
    """Eject disc from the specified drive."""
    from flask import request
    data = request.get_json(silent=True) or {}
    device = data.get("device", "")
    if not device:
        return jsonify({"error": "No device specified"}), 400
    success = eject_disc(device)
    return jsonify({"success": success})
