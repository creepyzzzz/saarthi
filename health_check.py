"""
Simple health check server to keep Render instance awake
Run this alongside your bot using a process manager or in a separate thread
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        pass  # Suppress logs

def run_health_check_server(port=8080):
    """Run health check server on specified port"""
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"🏥 Health check server running on port {port}")
    server.serve_forever()

def start_health_check():
    """Start health check server in background thread"""
    thread = threading.Thread(target=run_health_check_server, daemon=True)
    thread.start()
    return thread

