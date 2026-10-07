@echo off
setlocal EnableExtensions EnableDelayedExpansion
title EDSMT - Build
cd /d "%~dp0"
color 0E

echo.
echo   ==========================================================
echo      Building EDSMT
echo   ==========================================================
echo.
echo   You end up with two files in the upload folder:
echo.
echo      EDSMT-Setup.exe   ^<-- the download link on the website
echo      EDSMT.exe         ^<-- portable, for anyone who wants no installer
echo.
echo   Nothing here needs admin rights.
echo.

if not exist "edsmt.py" goto NOAPP

rem ---------------------------------------------------------------------
rem  1. Python
rem ---------------------------------------------------------------------
echo   [1/6] Looking for Python...
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
echo         OK.

rem ---------------------------------------------------------------------
rem  2. Inno Setup - found or fetched BEFORE anything is compiled, so a
rem     missing tool costs five seconds instead of five minutes.
rem ---------------------------------------------------------------------
echo   [2/6] Looking for Inno Setup, which builds the installer...
call :FINDINNO
if defined ISCC goto HAVEINNO

echo         Not installed. Fetching it with winget...
winget install -e --id JRSoftware.InnoSetup --accept-source-agreements --accept-package-agreements --silent >nul 2>&1
call :FINDINNO
if defined ISCC goto HAVEINNO

echo         winget could not. Downloading it from jrsoftware.org...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Invoke-WebRequest -Uri 'https://jrsoftware.org/download.php/is.exe' -OutFile \"$env:TEMP\innosetup.exe\" -UseBasicParsing } catch { exit 1 }"
if exist "%TEMP%\innosetup.exe" (
    echo         Installing it for your user only. Approve the prompt if one appears...
    "%TEMP%\innosetup.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER
    call :FINDINNO
)
if defined ISCC goto HAVEINNO
echo         COULD NOT GET IT. The portable EDSMT.exe will still be built,
echo         but there will be no EDSMT-Setup.exe. Install Inno Setup from
echo         https://jrsoftware.org/isdl.php and run this again.
goto AFTERINNO

:HAVEINNO
echo         OK.  !ISCC!

:AFTERINNO

rem ---------------------------------------------------------------------
rem  3. Build environment
rem ---------------------------------------------------------------------
echo   [3/6] Preparing the build environment...
if not exist ".venv-build\Scripts\python.exe" %PY% -m venv .venv-build
if errorlevel 1 goto FAIL
set "BPY=.venv-build\Scripts\python.exe"
"%BPY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%BPY%" -m pip install -r requirements.txt "pyinstaller>=6.0,<7" --quiet --disable-pip-version-check
if errorlevel 1 goto FAIL
rem The API's source is kept in the private folder beside this one. Where it
rem is, install its libraries too, so the API is tested before a release
rem rather than skipped. Best effort - a failure must not stop the build.
if exist "..\EDSMT-Private\server\requirements.txt" "%BPY%" -m pip install -r "..\EDSMT-Private\server\requirements.txt" --quiet --disable-pip-version-check >nul 2>&1
echo         OK.

rem  Bundles before 1.10028 put the internal documents at the top of this
rem  folder. Unzipping a newer one over them leaves the old copies behind,
rem  where they would go into the source zip and trip the private-term
rem  check. Move any that are still here into the private folder's
rem  old-copies - moved, not deleted, so nothing of yours is lost.
set "OLDCOPIES=internal\old-copies"
if exist "..\EDSMT-Private\" set "OLDCOPIES=..\EDSMT-Private\old-copies"
set "STALE="
for %%F in (BACKLOG.md DECISIONS.md DEVLOG.md RUNBOOK.md UPDATE-GUIDE.md DEPLOY-LIVE.md LEAK-TERMS.txt DISCORD-beta-1.10027.md) do if exist "%%F" set "STALE=1"
rem  The API's source left this folder in 1.10033. A copy still here would be
rem  zipped into the public source and could be uploaded by mistake.
if exist "server\" set "STALE=1"
if defined STALE (
    echo         Moving internal documents an older bundle left at the top
    echo         into the private folder's old-copies ...
    if not exist "%OLDCOPIES%" mkdir "%OLDCOPIES%"
    for %%F in (BACKLOG.md DECISIONS.md DEVLOG.md RUNBOOK.md UPDATE-GUIDE.md DEPLOY-LIVE.md LEAK-TERMS.txt DISCORD-beta-1.10027.md) do if exist "%%F" move /y "%%F" "%OLDCOPIES%\%%F" >nul
    if exist "server\" move "server" "%OLDCOPIES%\server-from-EDSMT-GitHub-%RANDOM%" >nul
)

rem ---------------------------------------------------------------------
rem  4. Tests. Nothing ships that has not passed.
rem ---------------------------------------------------------------------
echo   [4/6] Running the tests...
echo         Test windows open and close by themselves for a minute or
echo         two. Do not type or click until this step says OK - a key
echo         pressed now lands in one of them and fails a check.
"%BPY%" tests\run_all.py
if errorlevel 1 goto TESTSFAILED
echo         OK.

rem ---------------------------------------------------------------------
rem  5. Compile. Folder build for the installer, single file for portable.
rem ---------------------------------------------------------------------
echo   [5/6] Compiling. Two builds, a few minutes...
if exist "dist" rmdir /s /q "dist"
echo         ...the folder build, which goes inside the installer
"%BPY%" -m PyInstaller build\EDSMT.spec --noconfirm --distpath dist --workpath build\work
if errorlevel 1 goto FAIL
if not exist "dist\EDSMT\EDSMT.exe" goto FAIL
echo         ...the portable single file
"%BPY%" -m PyInstaller build\EDSMT-onefile.spec --noconfirm --distpath dist --workpath build\work
if errorlevel 1 goto FAIL
if not exist "dist\EDSMT.exe" goto FAIL
echo         OK.

rem ---------------------------------------------------------------------
rem  6. Package
rem ---------------------------------------------------------------------
echo   [6/6] Packaging for the website...
if exist "upload" rmdir /s /q "upload"
mkdir "upload"
copy /y "dist\EDSMT.exe" "upload\EDSMT.exe" >nul
if errorlevel 1 goto FAIL

if defined ISCC (
    echo         Building the installer...
    "!ISCC!" /Q "build\installer.iss"
    if errorlevel 1 (
        echo         Inno Setup reported a problem - see above. Carrying on
        echo         with the portable exe, which is unaffected.
    )
)

rem  The page has to name the build it is offering and say what changed,
rem  or an update is invisible to everybody who already has EDSMT. This
rem  also writes version.json, which is what the app checks on launch -
rem  AFTER the installer is built, because version.json carries the
rem  SHA-256 of both downloads and the app refuses a file that does not
rem  match it.
"%BPY%" build\site.py
if errorlevel 1 goto FAIL
if exist "site\index.html" copy /y "site\index.html" "upload\index.html" >nul
rem  The landing page. Written by hand, not generated, and it was sitting in
rem  site\ with nothing shipping it - so it existed and nobody could ever
rem  reach it. index.html is the download page the auto-updater points at;
rem  this is the page you link from radioraxxla.com.
if exist "site\edsmt.html" copy /y "site\edsmt.html" "upload\edsmt.html" >nul
rem  The pictures the page shows. Upload them with it.
for %%F in (site\*.jpg) do copy /y "%%F" "upload\%%~nxF" >nul
if exist "site\version.json" copy /y "site\version.json" "upload\version.json" >nul
if exist "radioraxxla.ico" copy /y "radioraxxla.ico" "upload\favicon.ico" >nul
if errorlevel 1 goto FAIL

rem  PyInstaller leaves its scratch tree in build\work - 20-odd MB of
rem  unpacked libraries that are not source and must not be in the source
rem  zip. The exclusion list below only sees top-level names, so build\work
rem  and the __pycache__ folders further down have to go before the zip runs.
if exist "build\work" rmdir /s /q "build\work"
for /d /r %%D in (__pycache__) do if exist "%%D" rmdir /s /q "%%D"

rem  The internal folder is excluded, and so is any internal document
rem  left at the top by mistake. They describe one server, and GPL-3.0
rem  asks for the source of the PROGRAM - not the notes on where it runs.
echo         Zipping the source, which GPL-3.0 requires you to offer...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$i = Get-ChildItem -Path . -Force | Where-Object { $_.Name -notin @('.venv','.venv-build','dist','upload','__pycache__','.git','internal','server','RUNBOOK.md','DEVLOG.md','DECISIONS.md','BACKLOG.md','UPDATE-GUIDE.md') }; Compress-Archive -Path $i.FullName -DestinationPath 'upload\EDSMT-source.zip' -CompressionLevel Optimal -Force"
echo         OK.

echo.
echo   ==========================================================
echo      Done. Upload everything below to radioraxxla.com/EDSMT/
echo      Upload version.json LAST. The app downloads a new build as soon
echo      as version.json names it, and checks it against the checksum in
echo      there - before the exes are up, every copy would fetch the old one,
echo      refuse it, and try again later.
echo.
for %%F in ("upload\*") do echo        %%~nxF   %%~zF bytes
echo.
if exist "upload\EDSMT-Setup.exe" (
    echo      EDSMT-Setup.exe is the download link.
) else (
    echo      NO INSTALLER was built - Inno Setup is missing.
    echo      EDSMT.exe still works on its own; use that link for now.
)
echo   ==========================================================
echo.
choice /c YN /m "   Open the upload folder"
if errorlevel 2 goto END
start "" "%CD%\upload"
goto END

rem ---------------------------------------------------------------------
:FINDINNO
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
exit /b 0

:TESTSFAILED
echo.
echo   TESTS FAILED - nothing was built. The failures are above.
echo.
pause
goto END

:GETPYTHON
echo.
echo   Python 3.10 or newer is needed to build.
where winget >nul 2>&1
if errorlevel 1 goto MANUALPY
choice /c YN /m "   Install Python now"
if errorlevel 2 goto MANUALPY
winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
echo.
echo   Installed. CLOSE this window and run this file again.
echo.
pause
goto END

:MANUALPY
echo.
echo   Get it from python.org, ticking "Add python.exe to PATH",
echo   then run this file again.
echo.
pause
start "" "https://www.python.org/downloads/"
goto END

:NOAPP
echo   PROBLEM: edsmt.py is not in this folder.
echo   This folder is: %CD%
echo.
pause
goto END

:FAIL
echo.
echo   BUILD FAILED. The error is above.
echo.
pause

:END
endlocal
