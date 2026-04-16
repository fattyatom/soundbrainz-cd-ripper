from flask import Blueprint, jsonify, request

from backend.config import load_config, update_config
from backend.services.library_service import detect_structure

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/settings", methods=["GET"])
def get_settings():
    """Return current settings."""
    return jsonify(load_config())


@settings_bp.route("/api/settings", methods=["POST"])
def post_settings():
    """Update settings."""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No data provided"}), 400

    config = update_config(data)
    return jsonify(config)


@settings_bp.route("/api/library/detect-structure", methods=["GET"])
def get_detect_structure():
    """Detect the folder structure of an existing music library.

    Query params:
        dir: Path to the music library root directory
    """
    directory = request.args.get("dir")
    if not directory:
        return jsonify({"error": "No directory specified"}), 400

    pattern = detect_structure(directory)
    return jsonify({"pattern": pattern, "directory": directory})
