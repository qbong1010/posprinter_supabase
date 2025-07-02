# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=collect_dynamic_libs("vcruntime140.dll"),
    datas=[
        ('src', 'src'), 
        ('printer_config.json', '.'), 
        ('version.json', '.'),
    ] + collect_data_files('escpos'),
    hiddenimports=['PySide6.QtCore', 'PySide6.QtWidgets', 'PySide6.QtGui', 'websockets', 'requests', 'python_escpos', 'psutil', 'pyusb', 'serial', 'escpos', 'escpos.capabilities', 'python-dotenv', 'dotenv', 'zoneinfo', 'pathlib', 'threading', 'signal', 'atexit', 'json', 'datetime', 'timedelta', 'src.utils'],
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
    name='POSPrinter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
