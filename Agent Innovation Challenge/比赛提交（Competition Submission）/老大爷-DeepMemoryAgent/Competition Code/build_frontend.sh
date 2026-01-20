#!/bin/bash
# Build script for frontend

cd frontend
npm install
npm run build
cd ..

echo "Frontend built successfully!"
