#!/usr/bin/env bash
cd "$(dirname "$0")/.."
sh scripts/start_backend.sh &
BACKEND_PID=$!
trap "kill $BACKEND_PID" EXIT
cd frontend
npm run dev
