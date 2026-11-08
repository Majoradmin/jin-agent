@echo off
title MobileLab - Local Firmware Workbench
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 goto RUNPY
where py >nul 2>nul
if %errorlevel%==0 goto RUNPYLAUNCH

echo.
echo  [MobileLab] Python nahi mila. Python 3.10+ install karain:
echo  https://www.python.org/downloads/  (install ke waqt "Add python.exe to PATH" tick karein)
echo.
pause
exit /b 1

:RUNPY
python server.py %*
goto END

:RUNPYLAUNCH
py server.py %*
goto END

:END
echo.
echo  MobileLab band ho gaya.
pause
