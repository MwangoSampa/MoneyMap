@echo off
title MoneyMap - tests
cd /d "%~dp0"
python -m pip install -q --disable-pip-version-check -r requirements-dev.txt
python -m pytest -v
echo.
echo ---- Security scan (Bandit) ----
python -m bandit -r . -x ./tests,./.venv -q
pause
