@echo off
REM Build script for frontend (Windows)

cd frontend
call npm install
call npm run build
cd ..

echo Frontend built successfully!
