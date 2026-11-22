@echo off
rem LP Toolkit web app. Add --lan to let other computers on the office network open it (http://<this computer>:5050)
cd /d "%~dp0"
rem close any older copy of the app still running on port 5050, so the latest version always starts
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5050" ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
start "" http://localhost:5050
"%~dp0env\Scripts\python.exe" "%~dp0webapp\app.py" %*
