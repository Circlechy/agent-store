@echo off
start "" %~dp0scripts\start_backend.bat
cd frontend
npm run dev
