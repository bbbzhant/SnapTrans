# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for 闪译 (SnapTrans).

Build:  uv run pyinstaller build.spec
Output: dist/闪译.exe  (single-file, no console window)
"""

import os

block_cipher = None

a = Analysis(
    [
        'main.py',
    ],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the icon for tray display (optional, tray icon is also generated at runtime)
        ('assets/icon.ico', 'assets'),
    ],
    hiddenimports=[
        # mss Windows backend
        'mss.windows',
        # PySide6 plugins (PyInstaller hooks handle most, but be explicit)
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'PySide6.QtCore',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused modules to reduce size
        'tkinter',
        'unittest',
        'test',
        'pydoc',
        'doctest',
        'pdb',
        'profile',
        'pstats',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='闪译',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        # UPX can corrupt Qt DLLs — exclude them
        'Qt6Core.dll',
        'Qt6Gui.dll',
        'Qt6Widgets.dll',
        'Qt6Network.dll',
        'shiboken6.abi3.dll',
        'python3.dll',
    ],
    runtime_tmpdir=None,
    console=False,          # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',  # Application icon
)
