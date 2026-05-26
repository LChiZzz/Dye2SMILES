# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


def collect_tree(src, dest):
    src_path = Path(src)
    collected = []
    if not src_path.exists():
        return collected

    for path in src_path.rglob('*'):
        if path.is_file():
            target_dir = Path(dest) / path.relative_to(src_path).parent
            collected.append((str(path), str(target_dir)))
    return collected


datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('rdkit')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
datas += collect_tree('packaging/osra-runtime', 'osra-runtime')


a = Analysis(
    ['packaging/lcsmiles_app.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Dye2SMILES',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Dye2SMILES',
)
app = BUNDLE(
    coll,
    name='Dye2SMILES.app',
    icon='assets/lcsmiles_icon.icns',
    bundle_identifier=None,
)
