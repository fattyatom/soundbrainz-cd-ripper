import logging
import os
import shutil
import subprocess
from flask import Flask, jsonify, send_from_directory

from backend.routes.drives import drives_bp
from backend.routes.rip import rip_bp
from backend.routes.lookup import lookup_bp
from backend.routes.settings import settings_bp

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = Flask(__name__, static_folder=None)

    # Register API blueprints
    app.register_blueprint(drives_bp)
    app.register_blueprint(rip_bp)
    app.register_blueprint(lookup_bp)
    app.register_blueprint(settings_bp)

    # Health check endpoint
    @app.route("/api/health", methods=["GET"])
    def health():
        deps = check_dependencies()
        healthy = all(d["installed"] for d in deps.values())
        return jsonify({"healthy": healthy, "dependencies": deps}), 200 if healthy else 503

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    # Serve frontend static files
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

    @app.route("/")
    def serve_index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        return send_from_directory(frontend_dir, path)

    # Log startup dependency status
    deps = check_dependencies()
    for name, info in deps.items():
        status = "OK" if info["installed"] else "MISSING"
        logger.info("Dependency %s: %s %s", name, status, info.get("version", ""))

    return app


def check_dependencies() -> dict:
    """Check if required system dependencies are available."""
    deps = {}

    # cdparanoia / cd-paranoia (macOS uses cd-paranoia from libcdio-paranoia)
    cd_paranoia = _check_command("cd-paranoia", ["cd-paranoia", "-V"])
    cdparanoia = _check_command("cdparanoia", ["cdparanoia", "-V"])
    if cd_paranoia["installed"]:
        deps["cdparanoia"] = cd_paranoia
        deps["cdparanoia"]["name"] = "cd-paranoia (libcdio)"
    elif cdparanoia["installed"]:
        deps["cdparanoia"] = cdparanoia
    else:
        deps["cdparanoia"] = {
            "installed": False,
            "version": "",
            "hint": "Install with: brew install libcdio-paranoia (macOS) or apt install cdparanoia (Linux)",
        }

    # ffmpeg
    deps["ffmpeg"] = _check_command("ffmpeg", ["ffmpeg", "-version"])

    # libdiscid (via python discid module)
    try:
        import discid
        deps["libdiscid"] = {"installed": True, "version": "available"}
    except (ImportError, OSError):
        deps["libdiscid"] = {
            "installed": False,
            "version": "",
            "hint": "Install with: brew install libdiscid (macOS) or apt install libdiscid-dev (Linux)",
        }

    return deps


def _check_command(name: str, cmd: list[str]) -> dict:
    """Check if a command-line tool is available."""
    path = shutil.which(cmd[0])
    if not path:
        hints = {
            "cdparanoia": "brew install cdparanoia (macOS) or apt install cdparanoia (Linux)",
            "ffmpeg": "brew install ffmpeg (macOS) or apt install ffmpeg (Linux)",
        }
        return {
            "installed": False,
            "version": "",
            "hint": f"Install with: {hints.get(name, 'check your package manager')}",
        }

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        # Extract first line of version output
        version_line = (result.stdout or result.stderr).splitlines()[0] if (result.stdout or result.stderr) else ""
        return {"installed": True, "version": version_line[:100]}
    except Exception:
        return {"installed": True, "version": "unknown"}
