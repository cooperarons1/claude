#!/usr/bin/env python3
"""
Simple web server for the EX Deoxys report dashboard.
Serves the static site and provides a JSON data endpoint.

Usage: python web_server.py [port]
Default port: 8080
"""

import http.server
import json
import os
import sys
import subprocess
import urllib.parse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(PROJECT_DIR, "static")
DATA_FILE = os.path.join(PROJECT_DIR, "ex_deoxys_full_report.json")


class ReportHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/data":
            self.serve_data()
        elif parsed.path == "/api/refresh":
            self.refresh_data()
        else:
            super().do_GET()

    def serve_data(self):
        """Serve the report JSON data."""
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                data = json.load(f)
            self.send_json(200, {"status": "ok", "cards": data})
        else:
            self.send_json(200, {"status": "no_data", "cards": []})

    def refresh_data(self):
        """Run the report script to regenerate data."""
        script = os.path.join(PROJECT_DIR, "ex_deoxys_report.py")
        if not os.path.exists(script):
            self.send_json(500, {"status": "error", "message": "Report script not found"})
            return

        try:
            result = subprocess.run(
                [sys.executable, script],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0 and os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    data = json.load(f)
                self.send_json(200, {
                    "status": "ok",
                    "cards": data,
                    "log": result.stdout[-2000:] if result.stdout else "",
                })
            else:
                self.send_json(500, {
                    "status": "error",
                    "message": result.stderr[-1000:] if result.stderr else "Script failed",
                    "log": result.stdout[-2000:] if result.stdout else "",
                })
        except subprocess.TimeoutExpired:
            self.send_json(500, {"status": "error", "message": "Report timed out (5m limit)"})

    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[server] {args[0]}")


def main():
    os.makedirs(STATIC_DIR, exist_ok=True)
    server = http.server.HTTPServer(("0.0.0.0", PORT), ReportHandler)
    print(f"EX Deoxys Report Dashboard")
    print(f"Serving at http://localhost:{PORT}")
    print(f"Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
