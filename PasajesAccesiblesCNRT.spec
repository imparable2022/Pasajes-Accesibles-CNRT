# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

playwright_datas, playwright_binaries, playwright_hidden = collect_all("playwright")
bs4_datas, bs4_binaries, bs4_hidden = collect_all("bs4")

block_cipher = None

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=playwright_binaries + bs4_binaries,
    datas=playwright_datas + bs4_datas,
    hiddenimports=playwright_hidden + bs4_hidden,
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
    name="Pasajes Accesibles CNRT",
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
    name="Pasajes Accesibles CNRT",
)
