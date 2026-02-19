@echo off
setlocal
echo ==============================================
echo Fourier Cycles WebApp - Debug Environment Tunnel
echo ==============================================

:: Default Configuration (Change as needed)
set SSH_USER=wasti
set SSH_HOST=beelink.telekom.ip

:: Remote ports on your Beelink server
set FOURIER_UI_REMOTE_PORT=3010
set DEVTOOLS_REMOTE_PORT=9222

:: Local ports on your Windows Development machine
set FOURIER_UI_LOCAL_PORT=3010
set DEVTOOLS_LOCAL_PORT=9222

echo [1] Launching SSH tunnels...
echo     Forwarding local UI port %FOURIER_UI_LOCAL_PORT% to remote %FOURIER_UI_REMOTE_PORT%
echo     Forwarding remote DevTools port %DEVTOOLS_REMOTE_PORT% to local %DEVTOOLS_LOCAL_PORT%

:: Start SSH Tunnel in background using start /b
:: -L : local port to remote port (for UI)
:: -R : remote port to local port (for DevTools)
start /b cmd /c "ssh -N -L %FOURIER_UI_LOCAL_PORT%:127.0.0.1:%FOURIER_UI_REMOTE_PORT% -R 127.0.0.1:%DEVTOOLS_REMOTE_PORT%:127.0.0.1:%DEVTOOLS_LOCAL_PORT% %SSH_USER%@%SSH_HOST%"

echo     Waiting 3 seconds for tunnel to establish...
timeout /t 3 /nobreak >nul

set MY_CHROME_DIR=%TEMP%\chrome-debug-fourier
echo [2] Opening Chrome in Debug mode (User Dir: %MY_CHROME_DIR%)
echo     Connect to http://localhost:%FOURIER_UI_LOCAL_PORT%
echo.

:: Launch Chrome with remote debugging, specific user data dir, to not interfere with your main browser.
start chrome --remote-debugging-port=%DEVTOOLS_LOCAL_PORT% --user-data-dir="%MY_CHROME_DIR%" "http://localhost:%FOURIER_UI_LOCAL_PORT%"

echo Setup complete. Close this window to keep the tunnel running, or kill the SSH process manually when done.
pause
endlocal
