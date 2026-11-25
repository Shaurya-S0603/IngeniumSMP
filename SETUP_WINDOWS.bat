@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements-host.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe setup_host.py configure
if errorlevel 1 goto fail
if exist world.zip (
 if not exist server\world\level.dat (
  .venv\Scripts\python.exe setup_host.py import-world world.zip
  if errorlevel 1 goto fail
 )
)
echo Setup complete. Follow README.md to install Java, Fabric, EasyAuth and configure Discord.
pause
exit /b 0
:fail
echo Setup failed. Read the error above.
pause
exit /b 1
