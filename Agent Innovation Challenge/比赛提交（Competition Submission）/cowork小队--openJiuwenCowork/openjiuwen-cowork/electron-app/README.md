# openJiuwen Desktop App

A macOS desktop application for openJiuwen AI File Assistant.

## Features

- Intuitive directory selection
- File browser with visual file/directory icons
- Query input for AI-powered file operations
- Real-time chat interface
- Suggestion chips for common tasks

## Prerequisites

1. **Python 3.12** - Required for the backend API
2. **Node.js** - Required for Electron

## Installation & Setup

### 1. Python Backend Setup

First, install Python dependencies:

```bash
# Activate the virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Electron App Setup

Install Electron and Node dependencies:

```bash
cd electron-app
npm install
cd ..
```

## Running the Application

You need to run both the Python backend server and the Electron app.

### Step 1: Start the Python API Server

In one terminal:

```bash
# Activate the virtual environment
source venv/bin/activate

# Start the API server
python3 api_server.py
```

You should see:
```
============================================================
openJiuwen API Server
============================================================

Configuration validated successfully!

Starting API server on http://localhost:5001
Press Ctrl+C to stop the server
```

### Step 2: Start the Electron App

In a separate terminal:

```bash
cd electron-app
npm start
```

The desktop app should now open with the UI interface.

## Using the App

1. **Select a Directory**: Click the "Select Directory" button and choose a folder
2. **View Files**: The sidebar will show all files in the selected directory
3. **Enter Queries**: Type what you want to do in the input field
4. **Use Suggestions**: Click suggestion chips for common tasks
5. **Double-click Files**: Double-click any file to view its contents

### Example Queries

- "List all files with their sizes"
- "Rename all .txt files to have lowercase names"
- "Find all Python files in the directory"
- "Show me the directory structure"
- "Count files by type"

## Project Structure

```
electron-app/
├── package.json          # Electron app configuration
├── main.js              # Main Electron process
├── preload.js           # Preload script for IPC
├── index.html           # HTML UI
├── renderer.js          # Frontend JavaScript
└── README.md            # This file

api_server.py            # Python Flask API server
```

## Troubleshooting

### "Backend Disconnected" Error

Make sure the Python API server is running:
```bash
source venv/bin/activate
python3 api_server.py
```

### Module Not Found Errors

Make sure you're using Python 3.12 and have installed all dependencies:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

## Development

To open DevTools for debugging:
```bash
npm run dev
```
