@echo off
setlocal

if "%WX_DISPATCH_PORT%"=="" set WX_DISPATCH_PORT=18765
if "%WX_DISPATCH_HOST%"=="" set WX_DISPATCH_HOST=127.0.0.1
if "%WX_DISPATCH_DEMO_MODE%"=="" set WX_DISPATCH_DEMO_MODE=true
if "%WX_DISPATCH_RESET_DEMO_ON_START%"=="" set WX_DISPATCH_RESET_DEMO_ON_START=false
set WX_DISPATCH_BASE_URL=http://%WX_DISPATCH_HOST%:%WX_DISPATCH_PORT%

echo [WX Dispatch] Resetting demo database...
python scripts\reset_demo_db.py
if errorlevel 1 (
  echo [WX Dispatch] reset_demo_db failed.
  exit /b 1
)

echo [WX Dispatch] Starting backend...
echo Dashboard:
echo %WX_DISPATCH_BASE_URL%/dashboard
echo React Admin Console:
echo http://127.0.0.1:5173
echo.
echo WeChat MiniApp API address:
echo http://你的局域网IP:%WX_DISPATCH_PORT%
echo Replace 你的局域网IP with this computer's LAN IP for real device preview.
echo.
echo Login accounts:
echo admin / admin123
echo dispatcher / dispatcher123
echo driver_demo is driver role and cannot login to admin console.
echo.
start "" "%WX_DISPATCH_BASE_URL%/dashboard"
python backend\main.py

endlocal
