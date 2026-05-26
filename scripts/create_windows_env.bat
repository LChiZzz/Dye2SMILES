@echo off
setlocal
cd /d "%~dp0\.."

where conda >nul 2>nul
if errorlevel 1 (
  echo conda was not found. Install Miniforge for Windows first:
  echo https://conda-forge.org/download/
  exit /b 1
)

conda env create -f environment-windows.yml
if errorlevel 1 (
  echo.
  echo If the environment already exists, run:
  echo conda env update -n lcsmiles-win -f environment-windows.yml
  exit /b 1
)

echo.
echo Environment created. Next commands:
echo conda activate lcsmiles-win
echo scripts\build_windows.bat
