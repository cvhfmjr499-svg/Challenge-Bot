@echo off
rem Startet die Live-Ansicht des Challenge-Bots (Windows). Fenster offen lassen.
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python -m bot live
pause
