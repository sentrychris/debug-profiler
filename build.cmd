@echo off
setlocal

set "UPX_VERSION=4.2.4"
set "UPX_RELEASE=upx-%UPX_VERSION%-win64"

set "SPEC_FILE=prospector.spec"
set "BUILD_DIR=.\build"
set "DIST_DIR=.\dist"

cd /d "%~dp0"
set "CWD=%cd%"

if not exist "%CWD%\%SPEC_FILE%" (
    echo This script must be run from the same directory containing %SPEC_FILE%
    exit /b 1
)

echo Building %SPEC_FILE%...

REM Check for UPX
echo Checking for UPX...
if not exist ".\%UPX_RELEASE%" (
    echo Downloading UPX
    curl -LO "https://github.com/upx/upx/releases/download/v%UPX_VERSION%/%UPX_RELEASE%.zip"
    tar -xf "%UPX_RELEASE%.zip"
    del "%UPX_RELEASE%.zip"
) else (
    echo UPX is available
)

REM Check build dir
if exist "%BUILD_DIR%" (
    echo Cleaning build directory...
    rd /s /q "%BUILD_DIR%"
)

REM Check dist dir
if exist "%DIST_DIR%" (
    echo Cleaning dist directory...
    rd /s /q "%DIST_DIR%"
)

pyinstaller %SPEC_FILE% --upx-dir ".\%UPX_RELEASE%"

echo Removing UPX
rd /s /q ".\%UPX_RELEASE%"

endlocal
pause
