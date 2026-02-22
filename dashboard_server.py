#!/usr/bin/env python3
"""
Simple web server to serve live FBA benchmark dashboard.
"""
import json
import os
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent
LOG_FILE = REPO_ROOT / "competition_run.log"
DASHBOARD_FILE = REPO_ROOT / "dashboard.html"

print(f"LOG_FILE: {LOG_FILE}")
print(f"LOG_FILE exists: {LOG_FILE.exists()}")
print(f"DASHBOARD_FILE: {DASHBOARD_FILE}")
print(f"DASHBOARD_FILE exists: {DASHBOARD_FILE.exists()}")
sys.stdout.flush()

class DashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        """Override to use stdout instead of stderr"""
        print(f"{self.address_string()} - {format % args}")
        sys.stdout.flush()
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        
        if parsed.path == "/":
            # Serve dashboard HTML
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            if DASHBOARD_FILE.exists():
                with open(DASHBOARD_FILE, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"<h1>Dashboard file not found</h1>")
            return
        
        elif parsed.path == "/api/log":
            # Return recent log content
            log_content = ""
            if LOG_FILE.exists():
                try:
                    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                        log_content = f.read()
                except Exception as e:
                    log_content = f"Error reading log: {str(e)}"
            else:
                log_content = "Log file not found at: " + str(LOG_FILE)
            
            response = json.dumps({"content": log_content, "success": True})
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(response.encode())
            return
        
        # Default: 404
        self.send_response(404)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not found")

if __name__ == "__main__":
    PORT = 8888
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"\n🚀 Dashboard server running at http://127.0.0.1:{PORT}")
    print(f"📊 Open this URL in your browser to watch live!")
    print(f"\nPress Ctrl+C to stop the server.\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Server stopped.")
