@echo off
echo Starting DiarizeStudio Backend and Frontend...
start "DiarizeStudio Backend" cmd /k "py -3.11 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
cd frontend
npm run dev
