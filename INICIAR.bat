@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime\pronto-v07.txt" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0preparar.ps1"
  if errorlevel 1 (
    echo.
    echo Falha na preparacao. Confira a mensagem acima e sua conexao.
    pause
    exit /b 1
  )
)
"%~dp0runtime\python.exe" "%~dp0app.py"
if errorlevel 1 pause
