@echo off
setlocal
where py.exe >nul 2>nul
if errorlevel 1 goto python
if "%~1"=="" goto defaultpy
py -3 "%~dp0devin_zh.py" %*
exit /b %errorlevel%
:defaultpy
py -3 "%~dp0devin_zh.py" apply
exit /b %errorlevel%
:python
where python.exe >nul 2>nul
if errorlevel 1 goto missing
if "%~1"=="" goto defaultpython
python "%~dp0devin_zh.py" %*
exit /b %errorlevel%
:defaultpython
python "%~dp0devin_zh.py" apply
exit /b %errorlevel%
:missing
echo Install Python 3.10 or later, then run this command again.
exit /b 1
