@echo off
cd /d "%~dp0"
py -3 bot.py run
exit /b %errorlevel%
