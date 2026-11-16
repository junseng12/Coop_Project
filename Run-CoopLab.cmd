@echo off
setlocal
pushd "%~dp0"
wsl.exe --exec bash scripts/run_local.sh %*
set "COOP_RC=%ERRORLEVEL%"
popd
exit /b %COOP_RC%
