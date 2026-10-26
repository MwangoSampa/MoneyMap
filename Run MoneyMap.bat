@echo off
title MoneyMap
cd /d "%~dp0"
where python >nul 2>nul || (
  echo Python is not installed. Download it from https://www.python.org/downloads/
  echo Tick "Add python.exe to PATH" during install, then run this file again.
  pause & exit /b 1
)
echo Checking MoneyMap packages (first time takes a minute)...
python -m pip install -q --disable-pip-version-check -r requirements.txt || (echo Could not install packages. Check your internet. & pause & exit /b 1)
echo Starting MoneyMap...
python main.py %*
if errorlevel 1 pause
