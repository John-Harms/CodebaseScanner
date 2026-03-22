# -*- mode: python ; coding: utf-8 -*-
import os, tiktoken

# Collect the .tiktoken encoding data files bundled with the package
tiktoken_data_dir = os.path.join(os.path.dirname(tiktoken.__file__), 'tiktoken_ext')
tiktoken_datas = [
    (os.path.join(root, f), os.path.join('tiktoken_ext', os.path.relpath(root, tiktoken_data_dir)))
    for root, _, files in os.walk(tiktoken_data_dir)
    for f in files
]

# Also grab the cached .tiktoken BPE files from the tiktoken cache directory
import tempfile, pathlib
cache_dir = pathlib.Path(os.environ.get('TIKTOKEN_CACHE_DIR', pathlib.Path.home() / '.tiktoken'))
tiktoken_cache_datas = [
    (str(f), 'tiktoken_cache')
    for f in cache_dir.glob('*')
    if f.is_file()
] if cache_dir.exists() else []


a = Analysis(
    ['QtCodeScannerApp.py'],
    pathex=[],
    binaries=[],
    datas=tiktoken_datas + tiktoken_cache_datas,
    hiddenimports=['tiktoken_ext.openai_public', 'tiktoken_ext'],
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
    a.binaries,
    a.datas,
    [],
    name='CodebaseScanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
