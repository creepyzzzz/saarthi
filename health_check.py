"""
Simple health check server to keep Render instance awake
Run this alongside your bot using a process manager or in a separate thread
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os
import time

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        pass  # Suppress logs

# Global server instance to keep it alive
_health_check_server = None

def run_health_check_server(port=None):
    """Run health check server on specified port"""
    global _health_check_server
    # Use Render's PORT environment variable if available, otherwise default to 8080
    if port is None:
        port = int(os.getenv('PORT', 8080))
    
    try:
        _health_check_server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"🏥 Health check server bound to port {port}")
        _health_check_server.serve_forever()
    except OSError as e:
        # Port might be in use or not accessible
        print(f"⚠️ Health check server failed to start on port {port}: {e}")
        # Try alternative port
        alt_port = 10000
        try:
            _health_check_server = HTTPServer(('0.0.0.0', alt_port), HealthCheckHandler)
            print(f"🏥 Health check server bound to alternative port {alt_port}")
            _health_check_server.serve_forever()
        except Exception as e2:
            print(f"⚠️ Health check server failed on alternative port: {e2}")

def start_health_check():
    """Start health check server in background thread - binds immediately for Render detection"""
    global _health_check_server
    # Get port from Render's PORT environment variable (required for Web Services)
    port = int(os.getenv('PORT', 8080))
    
    # Create and bind server immediately (before starting thread)
    # This ensures Render can detect the port during startup scan
    try:
        _health_check_server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"🏥 Health check server bound to port {port} (Render will detect this)")
        
        # Start serving in background thread
        thread = threading.Thread(target=_health_check_server.serve_forever, daemon=True)
        thread.start()
        
        # Give it a moment to fully start and be detected by Render
        time.sleep(0.5)
        
        return thread
    except OSError as e:
        print(f"⚠️ Health check server failed to bind to port {port}: {e}")
        # Try alternative port
        try:
            alt_port = 10000
            _health_check_server = HTTPServer(('0.0.0.0', alt_port), HealthCheckHandler)
            print(f"🏥 Health check server bound to alternative port {alt_port}")
            thread = threading.Thread(target=_health_check_server.serve_forever, daemon=True)
            thread.start()
            time.sleep(0.5)
            return thread
        except Exception as e2:
            print(f"⚠️ Health check server failed on alternative port: {e2}")
            return None

