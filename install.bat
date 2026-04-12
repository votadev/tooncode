@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo.
echo   ToonCode Installer — by VotaLab
echo.

:: Check Python
set PYTHON=
for %%p in (python python3 py) do (
    %%p --version >nul 2>&1 && (
        for /f "tokens=2" %%v in ('%%p --version 2^>^&1') do (
            set PYTHON=%%p
            echo   Python: %%v
        )
    )
)
if "%PYTHON%"=="" (
    echo   [ERROR] Python 3.10+ required
    echo   Install: https://www.python.org/downloads/
    exit /b 1
)

:: Install dir
set INSTALL_DIR=%USERPROFILE%\.tooncode

if exist "%INSTALL_DIR%\.git" (
    echo   Updating...
    cd /d "%INSTALL_DIR%" && git pull --quiet
) else (
    echo   Cloning ToonCode...
    git clone --depth 1 https://github.com/votalab/tooncode.git "%INSTALL_DIR%"
)

:: Install deps
echo   Installing dependencies...
%PYTHON% -m pip install --quiet --disable-pip-version-check -r "%INSTALL_DIR%\requirements.txt"

:: Create launcher in a PATH-accessible location
set BIN_DIR=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps
(
    echo @echo off
    echo %PYTHON% "%INSTALL_DIR%\tooncode.py" %%*
) > "%BIN_DIR%\tooncode.cmd"

echo.
echo   ToonCode installed!
echo   Run:    tooncode
echo   Update: cd %%USERPROFILE%%\.tooncode ^&^& git pull
echo.
