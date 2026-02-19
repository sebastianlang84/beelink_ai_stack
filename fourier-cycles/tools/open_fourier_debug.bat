@echo off
setlocal

REM Override values by setting environment vars before running this script.
if not defined SSH_USER set "SSH_USER=wasti"
if not defined SSH_HOST set "SSH_HOST=192.168.0.188"
if not defined SSH_PORT set "SSH_PORT=22"

if not defined FOURIER_UI_REMOTE_PORT set "FOURIER_UI_REMOTE_PORT=3010"
if not defined FOURIER_UI_LOCAL_PORT set "FOURIER_UI_LOCAL_PORT=13010"
if not defined DEVTOOLS_LOCAL_PORT set "DEVTOOLS_LOCAL_PORT=9222"
if not defined DEVTOOLS_REMOTE_PORT set "DEVTOOLS_REMOTE_PORT=9223"

set "CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if not exist "%CHROME_PATH%" (
  echo [ERROR] chrome.exe not found. Install Google Chrome or set CHROME_PATH in this file.
  exit /b 1
)

set "DEBUG_PROFILE=%LOCALAPPDATA%\chrome-mcp-profile"

echo [INFO] Launching Chrome in debug mode on 127.0.0.1:%DEVTOOLS_LOCAL_PORT% ...
start "" "%CHROME_PATH%" ^
  --remote-debugging-port=%DEVTOOLS_LOCAL_PORT% ^
  --user-data-dir="%DEBUG_PROFILE%" ^
  "http://127.0.0.1:%FOURIER_UI_LOCAL_PORT%"

echo [INFO] Starting SSH tunnel to %SSH_USER%@%SSH_HOST%:%SSH_PORT% ...
echo [INFO] Keep this terminal open while debugging.
echo [INFO] Local UI:  http://127.0.0.1:%FOURIER_UI_LOCAL_PORT%
echo [INFO] Remote DevTools endpoint on Linux: http://127.0.0.1:%DEVTOOLS_REMOTE_PORT%

ssh -NT ^
  -o ExitOnForwardFailure=yes ^
  -o ServerAliveInterval=30 ^
  -o ServerAliveCountMax=3 ^
  -L 127.0.0.1:%FOURIER_UI_LOCAL_PORT%:127.0.0.1:%FOURIER_UI_REMOTE_PORT% ^
  -R 127.0.0.1:%DEVTOOLS_REMOTE_PORT%:127.0.0.1:%DEVTOOLS_LOCAL_PORT% ^
  -p %SSH_PORT% ^
  %SSH_USER%@%SSH_HOST%

