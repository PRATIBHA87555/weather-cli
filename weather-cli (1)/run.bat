@echo off
chcp 65001 >nul
echo Installing requirements (first run only)...
python -m pip install -q -r requirements.txt
python weather.py %*
pause
