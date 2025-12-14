"""
Simple health check server to keep Render instance awake
Run this alongside your bot using a process manager or in a separate thread
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        pass  # Suppress logs

def run_health_check_server(port=None):
    """Run health check server on specified port"""
    # Use Render's PORT environment variable if available, otherwise default to 8080
    if port is None:
        port = int(os.getenv('PORT', 8080))
    
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"🏥 Health check server running on port {port}")
        server.serve_forever()
    except OSError as e:
        # Port might be in use or not accessible
        print(f"⚠️ Health check server failed to start on port {port}: {e}")
        # Try alternative port
        alt_port = 10000
        try:
            server = HTTPServer(('0.0.0.0', alt_port), HealthCheckHandler)
            print(f"🏥 Health check server running on alternative port {alt_port}")
            server.serve_forever()
        except Exception as e2:
            print(f"⚠️ Health check server failed on alternative port: {e2}")

def start_health_check():
    """Start health check server in background thread"""
    # Get port from environment or use default
    port = int(os.getenv('PORT', 8080))
    thread = threading.Thread(target=run_health_check_server, args=(port,), daemon=True)
    thread.start()
    return thread

