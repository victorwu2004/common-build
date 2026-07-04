@echo off
REM Build and run the Python container with Podman on Windows

setlocal

set IMAGE_NAME=python-hello
set CONTAINER_NAME=hello-container

echo.
echo ============================================================
echo   Python Hello World in Podman
echo ============================================================
echo.

REM Check if podman is installed
where podman >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Podman not installed
    echo Install from: https://podman.io/getting-started/installation
    exit /b 1
)

echo Podman found:
podman --version
echo.

REM Step 1: Build the image
echo [1/3] Building container image...
podman build -t %IMAGE_NAME% .
if %ERRORLEVEL% NEQ 0 exit /b 1
echo Image built: %IMAGE_NAME%
echo.

REM Step 2: Stop and remove old container if exists
echo [2/3] Cleaning up old containers...
podman stop %CONTAINER_NAME% 2>nul
podman rm %CONTAINER_NAME% 2>nul
echo Cleanup complete
echo.

REM Step 3: Run the container
echo [3/3] Running container...
echo (Press Ctrl+C to stop)
echo.

podman run ^
    --name %CONTAINER_NAME% ^
    --rm ^
    -e NAME="Podman User" ^
    -e INTERVAL="3" ^
    -e MESSAGE="Running in Podman rootless container!" ^
    %IMAGE_NAME%
