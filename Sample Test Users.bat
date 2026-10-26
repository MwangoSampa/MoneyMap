@echo off
title MoneyMap - sample test users
cd /d "%~dp0"
where python >nul 2>nul || (echo Python is not installed. See README.md & pause & exit /b 1)
python -m pip install -q --disable-pip-version-check -r requirements.txt || (echo Could not install packages. & pause & exit /b 1)
echo Creating fresh sample data dated today...
python tools\sample_users.py
echo.
echo   1  Thandi   PIN 48261  delivery rider + Saturday market, 3 slow days
echo   2  Sipho    PIN 73915  seasonal farm worker, paid every 2 weeks
echo   3  Grace    PIN 60418  street vendor, steady sales, airtime leaks
echo   4  New user            no data - test the first-time setup
echo.
set /p choice=Choose a test user (1-4): 
if "%choice%"=="1" set prof=thandi
if "%choice%"=="2" set prof=sipho
if "%choice%"=="3" set prof=grace
if "%choice%"=="4" set prof=newuser
if not defined prof (echo Please choose 1, 2, 3 or 4. & pause & exit /b 1)
python main.py --profile %prof%
if errorlevel 1 pause
