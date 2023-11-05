# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(['prospect.py'],
        binaries=None,
        hiddenimports=[],
        hookspath=None,
        runtime_hooks=None,
        excludes=None)

a.datas += [('prospect.ico', 'prospect.ico', 'DATA')]

pyz = PYZ(a.pure)

exe = EXE(pyz,
        a.scripts,
        a.binaries,
        a.datas,
        name='prospect',
        strip=False,
        upx=True,
        console=True,
        icon='prospect.ico',
        version='version.rc')
