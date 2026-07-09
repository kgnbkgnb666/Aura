@echo off
setlocal
cd /d "%~dp0"

set "AURA_PY=%USERPROFILE%\.conda\envs\aura\python.exe"

if exist "%AURA_PY%" (
  "%AURA_PY%" -m agentvoice app
) else (
  python -m agentvoice app
)

if errorlevel 1 (
  echo.
  echo AgentVoice failed to start.
  echo Make sure dependencies are installed, then try again.
  pause
)

