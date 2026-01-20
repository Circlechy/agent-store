"""Flask API server for OpenJiuwen Agent"""

import sys
import io
from pathlib import Path
from flask import Flask, Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from agent import OpenJiuwenAgent
from config.settings import validate_config, get_settings

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Global agent instance
agent = None

# Current working directory for file operations
current_working_dir = "."


def initialize_agent():
    """Initialize the OpenJiuwen Agent"""
    global agent
    if agent is None:
        # Validate configuration
        is_valid, message = validate_config()
        if not is_valid:
            print(f"Configuration error: {message}")
            return False

        try:
            print("Initializing OpenJiuwen Agent...")
            agent = OpenJiuwenAgent()
            print("Agent initialized successfully!")
            return True
        except Exception as e:
            print(f"Failed to initialize agent: {e}")
            return False
    return True


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'agent_initialized': agent is not None})


@app.route('/list-directory', methods=['POST'])
def list_directory():
    """List files in a directory"""
    try:
        data = request.get_json()
        directory_path = data.get('directory_path', '.')

        path = Path(directory_path)
        if not path.exists():
            return jsonify({'error': f'Directory does not exist: {directory_path}'}), 404
        if not path.is_dir():
            return jsonify({'error': f'Path is not a directory: {directory_path}'}), 400

        files = []
        for item in sorted(path.iterdir()):
            files.append({
                'name': item.name,
                'path': str(item),
                'type': 'directory' if item.is_dir() else 'file',
                'size': item.stat().st_size if item.is_file() else 0
            })

        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/read-file', methods=['POST'])
def read_file():
    """Read file content"""
    try:
        data = request.get_json()
        file_path = data.get('file_path')

        if not file_path:
            return jsonify({'error': 'file_path is required'}), 400

        path = Path(file_path)
        if not path.exists():
            return jsonify({'error': f'File does not exist: {file_path}'}), 404
        if not path.is_file():
            return jsonify({'error': f'Path is not a file: {file_path}'}), 400

        content = path.read_text(encoding='utf-8')
        return jsonify({'content': content})
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/execute', methods=['POST'])
def execute_query():
    """Execute a query using the agent"""
    global current_working_dir

    if not initialize_agent():
        return jsonify({'error': 'Failed to initialize agent. Check configuration.'}), 500

    try:
        data = request.get_json()
        query = data.get('query')
        current_dir = data.get('current_directory')

        if not query:
            return jsonify({'error': 'query is required'}), 400

        # Update current working directory if provided
        if current_dir:
            current_working_dir = current_dir
            # Change to that directory for relative path operations
            os.chdir(current_dir)

        # Execute the query
        response = agent.run(query)

        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stream', methods=['POST'])
def stream_query():
    """Stream query execution with real-time tool execution status"""
    global current_working_dir

    if not initialize_agent():
        return jsonify({'error': 'Failed to initialize agent. Check configuration.'}), 500

    try:
        data = request.get_json()
        query = data.get('query')
        current_dir = data.get('current_directory')

        if not query:
            return jsonify({'error': 'query is required'}), 400

        # Update current working directory if provided
        if current_dir:
            current_working_dir = current_dir
            # Change to that directory for relative path operations
            os.chdir(current_dir)

        import json

        def generate():
            """Generate streaming response"""
            try:
                for chunk in agent.stream(query):
                    # Convert chunk to JSON string
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("OpenJiuwen API Server")
    print("=" * 60)

    # Validate configuration
    is_valid, message = validate_config()
    if not is_valid:
        print(f"\nConfiguration error: {message}")
        print("\nPlease check your .env file configuration.")
        sys.exit(1)

    print("\nConfiguration validated successfully!")

    # Start the Flask server
    print("\nStarting API server on http://localhost:5001")
    print("Press Ctrl+C to stop the server\n")

    # Run the app
    app.run(host='0.0.0.0', port=5001, debug=False)
