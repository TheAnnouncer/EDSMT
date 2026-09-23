@echo off
setlocal EnableExtensions
title EDSMT - Surface Mining Survey
cd /d "%~dp0"
color 0E

echo.
echo   ==========================================================
echo      EDSMT - Surface Mining Survey
echo   ==========================================================
echo.
echo   Starting. First run takes a minute while it sets itself up.
echo.

if not exist "edsmt.py" goto NOAPP

set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
if not defined PY goto GETPYTHON
%PY% -c "import sys;raise SystemExit(sys.version_info[:2].__lt__((3,10)))" >nul 2>&1
if errorlevel 1 goto GETPYTHON

if not exist ".venv\Scripts\python.exe" (
    echo   Setting up...
    %PY% -m venv .venv
    if errorlevel 1 goto FAIL
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet --disable-pip-version-check
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet --disable-pip-version-check
    if errorlevel 1 goto FAIL
)

echo   Running.
echo.
".venv\Scripts\pythonw.exe" edsmt.py
if errorlevel 1 (
    echo.
    echo   It exited with an error. Running again so you can read it:
    echo.
    ".venv\Scripts\python.exe" edsmt.py
    pause
)
goto END

:GETPYTHON
echo.
echo   Python 3.10 or newer is needed.
where winget >nul 2>&1
if errorlevel 1 goto MANUAL
choice /c YN /m "   Install Python now"
if errorlevel 2 goto MANUAL
winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
echo.
echo   Installed. CLOSE this window and run this file again.
echo.
pause
goto END

:MANUAL
echo.
echo   Install Python from python.org, ticking "Add python.exe to PATH",
echo   then run this file again.
echo.
pause
start "" "https://www.python.org/downloads/"
goto END

:NOAPP
echo   PROBLEM: edsmt.py is not in this folder.
echo   This file must sit next to it. This folder is:
echo     %CD%
echo.
pause
goto END

:FAIL
echo.
echo   Setup failed. The error is above.
echo.
pause

:END
endlocal
