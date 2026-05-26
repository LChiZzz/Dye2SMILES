# Dye2SMILES Windows Build

This project can build a Windows desktop app with the same Tkinter UI and RDKit conversion logic as the macOS app.

Important limitation: PyInstaller cannot cross-build a Windows `.exe` from macOS. Run these steps on Windows 10/11.

## Build

Install Miniforge for Windows, then open "Miniforge Prompt":

```bat
cd path\to\Dye2SMILES
scripts\create_windows_env.bat
conda activate lcsmiles-win
scripts\build_windows.bat
```

The output is:

```text
dist\Dye2SMILES\Dye2SMILES.exe
```

## OSRA Image Recognition

RDKit is installed from conda-forge and bundled by PyInstaller. OSRA is different:

- SourceForge lists OSRA 2.2.4 Windows binaries as a purchase download.
- conda-forge currently does not provide a `win-64` OSRA package.
- Without OSRA, the Windows app still supports `.cdxml`, `.cdx`, `.mol`, `.sdf`, `.smi`, and `.smiles`.
- Screenshot/PDF recognition requires OSRA.

To bundle OSRA into the Windows app, place a Windows OSRA runtime here before running `scripts\build_windows.bat`:

```text
packaging\osra-runtime-win\
  bin\osra.exe
  bin\...
  lib\...
  share\chain.txt
  share\superatom.txt
  share\spelling.txt
```

The build script will package it as `osra-runtime`, and `lcsmiles.ocsr` will discover it automatically.

If you do not bundle OSRA, users can still set:

```bat
set OSRA_PATH=C:\path\to\osra.exe
```

## Verification

Before packaging, the Windows build script runs:

```bat
python -m pytest -q
```

The core tests cover RDKit canonicalization, dye-specific OSRA cleanup rules, abbreviation replacement, and stereochemistry preservation for `@`, `@@`, `/`, and `\`.
