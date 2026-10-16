@echo off
REM PhotoPhoenix - starts the app at low priority. Settings: config.toml / .env (see the .example files).
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
start "" /low pythonw -m photophoenix
