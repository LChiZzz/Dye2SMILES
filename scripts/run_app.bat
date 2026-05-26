@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%cd%\src;%PYTHONPATH%
python -m lcsmiles.gui
