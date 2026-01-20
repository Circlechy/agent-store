from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
import re
import json
import subprocess
from io import StringIO
import os

app = FastAPI()

# Predefined folder to search in
BASE_FOLDER = Path(os.getenv("BASE_FOLDER", "/var/lib/jenkins/workspace/fetch-project/"))

# Remote server configuration
REMOTE_SERVER = os.getenv("REMOTE_SERVER", "10.10.12.102")
REMOTE_USER = os.getenv("REMOTE_USER", "unknown-user")
REMOTE_PORT = os.getenv("REMOTE_PORT", "22")

class WriteFileRequest(BaseModel):
    filename: str
    content: str

@app.get("/get-file")
def get_file(filename: str = Query(..., min_length=1, description="Name of the file to retrieve")):
    # Search recursively for the file
    matches = list(BASE_FOLDER.rglob(filename))

    if not matches:
        raise HTTPException(status_code=404, detail="File not found")
    print("get file matches:", matches)
    # If multiple matches exist, take the first one
    file_path = matches[0]

    # Read file content
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {e}")

    return JSONResponse(content={
        "filename": file_path.name,
        "full_path": str(file_path),
        "content": content
    })

@app.post("/write-file")
def write_file(request: WriteFileRequest):
    # Create the file path in the base folder
    # Search recursively for the file
    matches = list(BASE_FOLDER.rglob(request.filename))

    if not matches:
        raise HTTPException(status_code=404, detail="File not found")

    # If multiple matches exist, take the first one
    file_path = matches[0]
    print("write file matches:", matches)
    # print("write file path:", file_path)
    # Ensure the file path is within the base folder (security check)
    try:
        file_path.resolve().relative_to(BASE_FOLDER.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="File path must be within the base folder")

    # Write to remote server via SSH
    try:

        # Write file to remote server using SSH cat redirection
        process = subprocess.Popen(
            ["ssh", f"{REMOTE_USER}@{REMOTE_SERVER}", f"cat > '{file_path}'"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=request.content.encode())
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, "ssh", stderr=stderr)

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error writing to remote server: {e.stderr.decode()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing to remote server: {e}")

    return JSONResponse(status_code=200 , content={
        "filename": file_path.name,
        "full_path": str(file_path),
        "remote_server": REMOTE_SERVER,
        "message": "File written successfully to remote server"
    })


