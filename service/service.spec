# -*- mode: python ; coding: utf-8 -*-


block_cipher = None

a = Analysis(['service.py'],
        binaries=None,
        hiddenimports=['win32timezone'],
        hookspath=None,
        runtime_hooks=[],
        excludes=None,
        cipher=block_cipher)

a.datas += [('prospect.ico', 'prospect.ico', 'DATA')]

pyz = PYZ(a.pure)

exe = EXE(pyz,
        a.scripts,
        a.binaries,
        a.datas,
        name='prospectservice',
        strip=False,
        upx=True,
        console=True,
        icon='prospect.ico',
        version='version.rc')
