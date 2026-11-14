@echo off
setlocal
cd /d "%~dp0.."
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo Python 3.10 ya naya chahiye. Koi pip install zaroori nahi.
  pause
  exit /b 1
)
echo JIN Agent console: http://127.0.0.1:8766
python -m jin_agent serve --open
pause
