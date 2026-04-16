#!/usr/bin/env python3
"""Entry point for the SoundBrainz CD Ripper application."""

from backend import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
