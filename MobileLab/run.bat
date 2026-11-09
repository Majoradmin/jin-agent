@echo off
setlocal
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
set "PYEXE=python"
goto CHECKVER

:RUNPYLAUNCH
set "PYEXE=py"
goto CHECKVER

:CHECKVER
REM Query the chosen interpreter for its major and minor version numbers.
REM MobileLab needs Python 3.10 or newer: it uses newer type hints (PEP 604
REM unions), so an older interpreter would fail when importing server.py.
REM for /f parses the two integers; they are read outside the loop, so no
REM delayed expansion is needed here.
set "PYMAJOR="
set "PYMINOR="
for /f "tokens=1,2" %%a in ('%PYEXE% -c "import sys;print(sys.version_info[0],sys.version_info[1])"') do (
    set "PYMAJOR=%%a"
    set "PYMINOR=%%b"
)
REM An empty value means the interpreter could not be queried.
if not defined PYMAJOR goto VERFAIL
if not defined PYMINOR goto VERFAIL
REM Coerce both values to pure numbers so the IF tests below cannot fall back
REM to a misleading string comparison; non-numeric text becomes 0.
set /a "PYMAJOR=PYMAJOR+0" 2>nul
set /a "PYMINOR=PYMINOR+0" 2>nul
REM Reject anything older than 3.10; accept 3.10+ and any later major.
if %PYMAJOR% LSS 3 goto TOOOLD
if %PYMAJOR% GTR 3 goto RUN
if %PYMINOR% LSS 10 goto TOOOLD
goto RUN

:TOOOLD
echo.
echo  [MobileLab] Python 3.10 or newer is required. Found: %PYMAJOR%.%PYMINOR%
echo  MobileLab uses Python 3.10+ type hints and cannot run on older Python.
echo  Download: https://www.python.org/downloads/
echo.
pause
exit /b 1

:VERFAIL
echo.
echo  [MobileLab] Could not read the Python version. Python 3.10+ is required.
echo  Download: https://www.python.org/downloads/
echo.
pause
exit /b 1

:RUN
%PYEXE% server.py %*
goto END

:END
echo.
echo  MobileLab band ho gaya.
pause
