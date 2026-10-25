@echo off
setlocal

rem Double-click launcher. Creates a virtual environment on first run,
rem installs the requirements, then starts the app without a console window.

cd /d "%~dp0"

set "VENV=%~dp0.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PYW=%VENV%\Scripts\pythonw.exe"
set "STAMP=%VENV%\.requirements-installed"

rem --- locate a Python to build the environment with -------------------------
set "BOOTSTRAP="
where py >nul 2>&1 && set "BOOTSTRAP=py -3"
if not defined BOOTSTRAP (
    where python >nul 2>&1 && set "BOOTSTRAP=python"
)
if not defined BOOTSTRAP (
    echo Python was not found on this PC.
    echo Install it from https://www.python.org/downloads/ and tick
    echo "Add python.exe to PATH", then run this file again.
    pause
    exit /b 1
)

rem --- create the environment once -------------------------------------------
if not exist "%PY%" (
    echo Setting up for first use. This takes a minute...
    %BOOTSTRAP% -m venv "%VENV%" || goto :failed
)

rem --- install or refresh requirements when they change ----------------------
set "NEEDS_INSTALL=1"
if exist "%STAMP%" (
    for /f "usebackq delims=" %%H in (`certutil -hashfile "%~dp0requirements.txt" MD5 ^| find /v ":"`) do (
        set "HASH=%%H"
        goto :compare
    )
)
:compare
if defined HASH (
    set /p SAVED=<"%STAMP%" 2>nul
    if "%SAVED%"=="%HASH%" set "NEEDS_INSTALL="
)

if defined NEEDS_INSTALL (
    echo Installing requirements...
    "%PY%" -m pip install --upgrade pip --quiet
    "%PY%" -m pip install -r "%~dp0requirements.txt" || goto :failed
    if defined HASH (
        >"%STAMP%" echo %HASH%
    ) else (
        for /f "usebackq delims=" %%H in (`certutil -hashfile "%~dp0requirements.txt" MD5 ^| find /v ":"`) do (
            >"%STAMP%" echo %%H
            goto :launch
        )
    )
)

:launch
if exist "%PYW%" (
    start "" "%PYW%" "%~dp0gui.py"
) else (
    "%PY%" "%~dp0gui.py"
)
exit /b 0

:failed
echo.
echo Setup failed. Scroll up for the error.
pause
exit /b 1
