@echo off
setlocal
set "MC_AUDIO_PROVIDER_POLICY=1"
set "MC_CONTACT_AUDIO_TRACE=1"
call "%~dp0Play.cmd"
exit /b %errorlevel%
