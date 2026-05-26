# Windows OSRA Runtime Placeholder

This directory contains or accepts a Windows OSRA runtime before running `scripts\build_windows.bat`.

The current project can use the older SourceForge OSRA 1.3.9 Windows installer contents for basic screenshot recognition. OSRA 2.2.4 Windows binaries are listed by the upstream project as a purchase download.

Expected layout:

```text
osra-runtime-win\
  bin\osra.exe
  bin\...
  lib\...
  share\chain.txt
  share\superatom.txt
  share\spelling.txt
```

Without this runtime, the Windows app can still convert ChemDraw, MOL, SDF, SMI, and SMILES files. Image recognition will require `OSRA_PATH` to point to an installed `osra.exe`.
