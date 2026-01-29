"""Simple web server for the Discovery Agent dashboard."""

import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
import urllib.parse

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import SOW generator
from discovery_agent.sow_generator import generate_sow, SOWRequest


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for the dashboard."""
    
    def __init__(self, *args, output_dirs: list[Path] = None, **kwargs):
        self.output_dirs = output_dirs or []
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        print(f"[Dashboard] {self.command} {self.path}")
        
        if path == '/' or path == '/index.html':
            self.serve_dashboard()
        elif path == '/api/scans':
            self.serve_scans_api()
        elif path.startswith('/api/scan/'):
            scan_name = path.replace('/api/scan/', '')
            self.serve_scan_detail(scan_name)
        else:
            print(f"[Dashboard] 404 - path not matched: {path}")
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/api/sow/generate':
            self.handle_sow_generate()
        else:
            self.send_error(404, 'Endpoint not found')
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def handle_sow_generate(self):
        """Handle SOW generation request."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            request_data = json.loads(body.decode('utf-8'))
            
            # Validate request
            if not request_data.get('selected_project_ids'):
                self.send_json_error(400, "No projects selected")
                return
            
            if not request_data.get('discovery'):
                self.send_json_error(400, "Discovery data is required")
                return
            
            # Check if we should use mock 
            # Allow explicit mock request OR fallback if no Azure OpenAI configured
            force_mock = request_data.get('use_mock', False)
            azure_configured = bool(os.getenv('AZURE_OPENAI_ENDPOINT') and os.getenv('AZURE_OPENAI_API_KEY'))
            use_mock = force_mock or not azure_configured
            
            if force_mock:
                print("[SOW] Using mock generator (explicitly requested)")
            elif not azure_configured:
                print("[SOW] Using mock generator (Azure OpenAI not configured)")
            else:
                print("[SOW] Using Azure OpenAI for generation")
            
            # Generate SOW
            sow_request: SOWRequest = {
                'selected_project_ids': request_data['selected_project_ids'],
                'discovery': request_data['discovery'],
                'sow_options': request_data.get('sow_options', {})
            }
            
            result = generate_sow(sow_request, use_mock=use_mock)
            
            # Debug: log markdown length
            markdown_len = len(result.get('markdown', '')) if result.get('markdown') else 0
            print(f"[SOW] Markdown content length: {markdown_len} chars")
            if markdown_len < 100:
                print(f"[SOW] WARNING: Very short markdown: {result.get('markdown', '')[:100]}")
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
            
            print(f"[SOW] Generated SOW with {result['summary']['projects_count']} projects")
            
        except ValueError as e:
            self.send_json_error(400, str(e))
        except Exception as e:
            print(f"[SOW] Error: {e}")
            self.send_json_error(500, f"SOW generation failed: {str(e)}")
    
    def send_json_error(self, status_code: int, message: str):
        """Send a JSON error response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}).encode('utf-8'))
    
    def serve_dashboard(self):
        """Serve the main dashboard HTML."""
        template_path = Path(__file__).parent / 'templates' / 'dashboard.html'
        
        if template_path.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(template_path.read_bytes())
        else:
            self.send_error(404, 'Dashboard template not found')
    
    def serve_scans_api(self):
        """Serve list of all scans as JSON."""
        scans = []
        
        for output_dir in self.output_dirs:
            inventory_path = output_dir / 'inventory.json'
            if inventory_path.exists():
                try:
                    with open(inventory_path, 'r') as f:
                        inventory = json.load(f)
                        scans.append(inventory)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Failed to load {inventory_path}: {e}")
        
        # Sort by date descending
        scans.sort(key=lambda x: x.get('run', {}).get('started_at', ''), reverse=True)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(scans).encode('utf-8'))
    
    def serve_scan_detail(self, scan_name: str):
        """Serve details of a specific scan."""
        for output_dir in self.output_dirs:
            if output_dir.name == scan_name:
                inventory_path = output_dir / 'inventory.json'
                if inventory_path.exists():
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(inventory_path.read_bytes())
                    return
        
        self.send_error(404, f'Scan "{scan_name}" not found')
    
    def log_message(self, format: str, *args):
        """Suppress default logging, use custom format."""
        print(f"[Dashboard] {args[0]}")


def find_output_dirs(base_path: Path) -> list[Path]:
    """Find all directories containing inventory.json files."""
    output_dirs = []
    
    # Check direct children
    for item in base_path.iterdir():
        if item.is_dir():
            inventory_path = item / 'inventory.json'
            if inventory_path.exists():
                output_dirs.append(item)
    
    # Also check if base_path itself has inventory.json
    if (base_path / 'inventory.json').exists():
        output_dirs.append(base_path)
    
    return output_dirs


def create_handler(output_dirs: list[Path]):
    """Create a handler class with the output directories bound."""
    class BoundHandler(DashboardHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, output_dirs=output_dirs, **kwargs)
    return BoundHandler


def run_server(host: str = 'localhost', port: int = 8080, scan_dir: Path = None):
    """Run the dashboard web server."""
    if scan_dir is None:
        scan_dir = Path.cwd()
    
    # Find all output directories
    output_dirs = find_output_dirs(scan_dir)
    
    if not output_dirs:
        print(f"⚠️  No inventory.json files found in {scan_dir}")
        print("   Run a discovery scan first, then start the dashboard.")
        return
    
    print(f"📊 Found {len(output_dirs)} scan(s):")
    for d in output_dirs:
        print(f"   • {d.name}")
    
    handler = create_handler(output_dirs)
    server = HTTPServer((host, port), handler)
    
    print()
    print(f"🚀 Dashboard running at http://{host}:{port}")
    print(f"   Press Ctrl+C to stop")
    print()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        server.shutdown()


if __name__ == '__main__':
    run_server()
