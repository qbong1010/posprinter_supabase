# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src', 'src'), 
        ('printer_config.json', '.'), 
        ('version.json', '.'),
        ('venv\\Lib\\site-packages\\escpos\\capabilities.json', 'escpos')
    ],
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
