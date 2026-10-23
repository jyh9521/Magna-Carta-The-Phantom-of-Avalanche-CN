@echo off
setlocal
set "LOG=%~dp0Overlay-Launch-Fix.log"
echo Applying overlay launch repair...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Overlay-Launch-Fix-20261023\Update.ps1" -Runtime "%~dp0." >"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo.
type "%LOG%"
echo.
echo Update exit code: %RC%
echo Log: "%LOG%"
echo Press any key to close this window.
pause >nul
exit /b %RC%
