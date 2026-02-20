@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Override values by setting environment vars before running this script.
if not defined SSH_USER set "SSH_USER=wasti"
if not defined SSH_HOST set "SSH_HOST=192.168.0.188"
if not defined SSH_PORT set "SSH_PORT=22"
if not defined SSH_KEY_PATH set "SSH_KEY_PATH=%USERPROFILE%\.ssh\id_ed25519_fourier"
if not defined SSH_STRICT_HOST_KEY_CHECKING set "SSH_STRICT_HOST_KEY_CHECKING=accept-new"
if not defined SSH_CONNECT_TIMEOUT_SEC set "SSH_CONNECT_TIMEOUT_SEC=8"

if not defined FOURIER_UI_REMOTE_PORT set "FOURIER_UI_REMOTE_PORT=3010"
if not defined DEVTOOLS_LOCAL_PORT set "DEVTOOLS_LOCAL_PORT=9222"
if not defined DEVTOOLS_REMOTE_PORT set "DEVTOOLS_REMOTE_PORT=9223"
if not defined TUNNEL_RETRY_DELAY_SEC set "TUNNEL_RETRY_DELAY_SEC=5"
if not defined LOCAL_DEVTOOLS_WAIT_MAX_SEC set "LOCAL_DEVTOOLS_WAIT_MAX_SEC=20"
if not defined DEVTOOLS_REMOTE_PORT_SPAN set "DEVTOOLS_REMOTE_PORT_SPAN=10"

set "CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if not exist "%CHROME_PATH%" (
  echo [ERROR] chrome.exe not found. Install Google Chrome or set CHROME_PATH in this file.
  pause
  exit /b 1
)

set "DEBUG_PROFILE=%LOCALAPPDATA%\chrome-mcp-profile"
set "SSH_ERR_FILE=%TEMP%\fourier_debug_ssh.err"
set "CURRENT_DEVTOOLS_REMOTE_PORT=%DEVTOOLS_REMOTE_PORT%"

if not exist "%SSH_KEY_PATH%" (
  echo [ERROR] SSH key not found: %SSH_KEY_PATH%
  echo [ERROR] Create/import key first or set SSH_KEY_PATH before running this script.
  pause
  exit /b 1
)

echo [INFO] Starting SSH tunnel to %SSH_USER%@%SSH_HOST%:%SSH_PORT% ...
echo [INFO] Keep this terminal open while debugging.
echo [INFO] Target UI:  http://%SSH_HOST%:%FOURIER_UI_REMOTE_PORT%
echo [INFO] Remote DevTools endpoint on Linux: http://127.0.0.1:!CURRENT_DEVTOOLS_REMOTE_PORT!
echo [INFO] SSH key: %SSH_KEY_PATH%
echo [INFO] SSH host key policy: %SSH_STRICT_HOST_KEY_CHECKING%

call :check_ssh_auth
if errorlevel 1 (
  pause
  exit /b 1
)

call :ensure_local_devtools

set /a TUNNEL_ATTEMPT=0
:tunnel_loop
set /a TUNNEL_ATTEMPT+=1
echo [INFO] Tunnel attempt !TUNNEL_ATTEMPT! ...
echo [INFO] Trying remote DevTools port !CURRENT_DEVTOOLS_REMOTE_PORT! ...

ssh -NT ^
  -n ^
  -i "%SSH_KEY_PATH%" ^
  -o BatchMode=yes ^
  -o IdentitiesOnly=yes ^
  -o PreferredAuthentications=publickey ^
  -o StrictHostKeyChecking=%SSH_STRICT_HOST_KEY_CHECKING% ^
  -o ConnectTimeout=%SSH_CONNECT_TIMEOUT_SEC% ^
  -o ConnectionAttempts=1 ^
  -o LogLevel=ERROR ^
  -o ExitOnForwardFailure=yes ^
  -o ServerAliveInterval=30 ^
  -o ServerAliveCountMax=3 ^
  -R 127.0.0.1:!CURRENT_DEVTOOLS_REMOTE_PORT!:127.0.0.1:%DEVTOOLS_LOCAL_PORT% ^
  -p %SSH_PORT% ^
  %SSH_USER%@%SSH_HOST% 2>"!SSH_ERR_FILE!"

set "SSH_EXIT_CODE=!ERRORLEVEL!"
if "!SSH_EXIT_CODE!"=="255" (
  findstr /C:"remote port forwarding failed for listen port" "!SSH_ERR_FILE!" >nul
  if not errorlevel 1 (
    echo [WARN] Remote DevTools port !CURRENT_DEVTOOLS_REMOTE_PORT! is busy.
  )
)
echo [WARN] SSH tunnel ended (exit !SSH_EXIT_CODE!). Retrying in %TUNNEL_RETRY_DELAY_SEC%s ...
call :advance_remote_port
timeout /t %TUNNEL_RETRY_DELAY_SEC% /nobreak >nul
call :ensure_local_devtools
goto :tunnel_loop

pause


:check_ssh_auth
echo [INFO] Verifying SSH key auth ...
ssh ^
  -n ^
  -i "%SSH_KEY_PATH%" ^
  -o BatchMode=yes ^
  -o IdentitiesOnly=yes ^
  -o PreferredAuthentications=publickey ^
  -o StrictHostKeyChecking=%SSH_STRICT_HOST_KEY_CHECKING% ^
  -o ConnectTimeout=%SSH_CONNECT_TIMEOUT_SEC% ^
  -o ConnectionAttempts=1 ^
  -o LogLevel=ERROR ^
  -p %SSH_PORT% ^
  %SSH_USER%@%SSH_HOST% "exit 0" >nul
if errorlevel 1 (
  echo [ERROR] SSH key auth failed for %SSH_USER%@%SSH_HOST%:%SSH_PORT%.
  echo [ERROR] Verify authorized_keys on Linux or set SSH_KEY_PATH correctly.
  pause
  exit /b 1
)
goto :eof

:start_chrome_debug
echo [INFO] Launching Chrome in debug mode on 127.0.0.1:%DEVTOOLS_LOCAL_PORT% ...
start "" "%CHROME_PATH%" ^
  --remote-debugging-address=127.0.0.1 ^
  --remote-debugging-port=%DEVTOOLS_LOCAL_PORT% ^
  --no-first-run ^
  --no-default-browser-check ^
  --user-data-dir="%DEBUG_PROFILE%" ^
  "http://%SSH_HOST%:%FOURIER_UI_REMOTE_PORT%"
goto :eof

:ensure_local_devtools
set /a WAITED_SEC=0
:ensure_local_devtools_loop
call :is_local_devtools_ready
if not errorlevel 1 (
  goto :eof
)
if !WAITED_SEC! EQU 0 (
  call :start_chrome_debug
  echo [INFO] Waiting for local Chrome debug port 127.0.0.1:%DEVTOOLS_LOCAL_PORT% ...
)
if !WAITED_SEC! GEQ %LOCAL_DEVTOOLS_WAIT_MAX_SEC% (
  echo [WARN] Local Chrome DevTools endpoint on 127.0.0.1:%DEVTOOLS_LOCAL_PORT% is not reachable yet. Trying SSH anyway.
  goto :eof
)
timeout /t 1 /nobreak >nul
set /a WAITED_SEC+=1
goto :ensure_local_devtools_loop

:is_local_devtools_ready
curl --silent --fail --max-time 1 "http://127.0.0.1:%DEVTOOLS_LOCAL_PORT%/json/version" >nul 2>&1
if not errorlevel 1 (
  exit /b 0
)
REM Fallback if curl is missing: detect a listening TCP socket via foreign address 0.0.0.0:0 (locale-independent).
netstat -ano -p tcp | findstr /R /C:"127\.0\.0\.1:%DEVTOOLS_LOCAL_PORT% .*0\.0\.0\.0:0" >nul
if not errorlevel 1 (
  exit /b 0
)
exit /b 1

:advance_remote_port
set /a REMOTE_PORT_MAX=%DEVTOOLS_REMOTE_PORT% + %DEVTOOLS_REMOTE_PORT_SPAN%
set /a NEXT_REMOTE_PORT=!CURRENT_DEVTOOLS_REMOTE_PORT! + 1
if !NEXT_REMOTE_PORT! GTR !REMOTE_PORT_MAX! (
  set /a NEXT_REMOTE_PORT=%DEVTOOLS_REMOTE_PORT%
)
if !NEXT_REMOTE_PORT! NEQ !CURRENT_DEVTOOLS_REMOTE_PORT! (
  set "CURRENT_DEVTOOLS_REMOTE_PORT=!NEXT_REMOTE_PORT!"
  echo [WARN] Next remote DevTools endpoint: http://127.0.0.1:!CURRENT_DEVTOOLS_REMOTE_PORT!
)
goto :eof
