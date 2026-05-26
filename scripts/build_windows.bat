@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Miniforge/conda and create the lcsmiles-win environment first.
  exit /b 1
)

python -m pip install -e ".[dev]"
if errorlevel 1 exit /b 1

python -m pytest -q
if errorlevel 1 exit /b 1

if not exist "packaging\osra-runtime-win\bin\osra.exe" (
  echo.
  echo WARNING: packaging\osra-runtime-win\bin\osra.exe was not found.
  echo The Windows app will still support ChemDraw/MOL/SDF/SMILES, but screenshot/PDF recognition will require OSRA_PATH.
  echo Put a Windows OSRA runtime in packaging\osra-runtime-win to bundle image recognition.
  echo.
)

python -m PyInstaller --noconfirm LCSMILES_windows.spec
if errorlevel 1 exit /b 1

echo.
echo Built Windows app:
echo %cd%\dist\Dye2SMILES\Dye2SMILES.exe
