@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
  if not errorlevel 1 goto install
  echo Existing virtual environment is broken or too old. Rename .venv and retry.
  goto fail
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
  if not errorlevel 1 goto use_py
)
where python >nul 2>&1
if not errorlevel 1 (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
  if not errorlevel 1 goto use_python
)
echo Python 3.10 or newer not found. Install Python 3.12 from python.org and add it to PATH.
echo Reopen PowerShell after installation.
goto fail
:use_py
py -3 -m venv .venv
if errorlevel 1 goto fail
goto install
:use_python
python -m venv .venv
if errorlevel 1 goto fail
:install
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
