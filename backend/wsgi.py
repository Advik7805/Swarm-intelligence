"""
HiveMind WSGI entry point (for gunicorn / production servers).

Usage:
    gunicorn wsgi:app --workers 1 --threads 8 --bind 0.0.0.0:$PORT

Note on workers: the simulation manager keeps run state in memory, so the
app must run as a SINGLE worker (scale threads, not workers).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), threaded=True)
