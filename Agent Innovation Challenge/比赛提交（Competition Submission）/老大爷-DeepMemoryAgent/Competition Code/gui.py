"""GUI entry point that serves both frontend and API."""

import os
import threading
import webbrowser
import time
from pathlib import Path

from flask import Flask, send_from_directory, send_file, request
from flask_cors import CORS
import requests
import uvicorn

# Import FastAPI app
from api_server import app as fastapi_app

# Create Flask app
flask_app = Flask(__name__, static_folder=None)
CORS(flask_app)

# Frontend build directory
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"


def run_fastapi():
    """Run FastAPI server in a separate thread."""
    import uvicorn
    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="info")


@flask_app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy_api(path):
    """Proxy API requests to FastAPI server."""
    # Forward request to FastAPI
    url = f"http://127.0.0.1:8000/api/{path}"
    
    # Get query parameters
    if request.query_string:
        url += f"?{request.query_string.decode()}"
    
    # Forward headers (remove Host header)
    headers = {k: v for k, v in request.headers.items() if k != 'Host'}
    
    # Get request data
    json_data = None
    if request.is_json:
        json_data = request.get_json()
    
    # Make request
    try:
        if request.method == 'GET':
            resp = requests.get(url, headers=headers, params=request.args, timeout=30)
        elif request.method == 'POST':
            resp = requests.post(url, headers=headers, json=json_data, params=request.args, timeout=30)
        elif request.method == 'PUT':
            resp = requests.put(url, headers=headers, json=json_data, params=request.args, timeout=30)
        elif request.method == 'DELETE':
            resp = requests.delete(url, headers=headers, params=request.args, timeout=30)
        elif request.method == 'PATCH':
            resp = requests.patch(url, headers=headers, json=json_data, params=request.args, timeout=30)
        elif request.method == 'OPTIONS':
            resp = requests.options(url, headers=headers, params=request.args, timeout=30)
        else:
            return {'error': 'Method not allowed'}, 405
        
        # Return response with content type
        response_headers = dict(resp.headers)
        response_headers.pop('Content-Encoding', None)
        response_headers.pop('Transfer-Encoding', None)
        
        return (resp.content, resp.status_code, response_headers)
    except requests.exceptions.ConnectionError:
        return {'error': 'API server not available. Make sure FastAPI is running.'}, 503
    except Exception as e:
        return {'error': f'Proxy error: {str(e)}'}, 500


@flask_app.route('/', defaults={'path': ''})
@flask_app.route('/<path:path>')
def serve_frontend(path):
    """Serve frontend static files."""
    if path and (FRONTEND_DIST / path).exists():
        return send_from_directory(str(FRONTEND_DIST), path)
    else:
        # Serve index.html for all other routes (SPA routing)
        index_path = FRONTEND_DIST / 'index.html'
        if index_path.exists():
            return send_file(str(index_path))
        else:
            return "Frontend not built. Please run 'npm run build' in the frontend directory.", 500


def main():
    """Main entry point."""
    # Check if frontend is built
    if not (FRONTEND_DIST / 'index.html').exists():
        print("ERROR: Frontend not built!")
        print("Please run the following commands:")
        print("  cd frontend")
        print("  npm install")
        print("  npm run build")
        return
    
    # Start FastAPI server in background thread
    print("Starting FastAPI server on http://127.0.0.1:8000...")
    api_thread = threading.Thread(target=run_fastapi, daemon=True)
    api_thread.start()
    
    # Give FastAPI time to start
    import time
    time.sleep(1)
    
    # Start Flask server
    print("\n" + "="*60)
    print("DeepMemory Agent GUI")
    print("="*60)
    print("Flask server: http://127.0.0.1:5000")
    print("FastAPI server: http://127.0.0.1:8000")
    print("Opening browser...")
    print("="*60 + "\n")
    
    # Open browser after a short delay
    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://127.0.0.1:5000')
    
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Run Flask app
    flask_app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
