# -*- mode: python ; coding: utf-8 -*-
a=Analysis(['app/main.py'],pathex=[],binaries=[],datas=[('app/web','web')],hiddenimports=['feedparser','requests'],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='HiUltimateLiteV4',debug=False,bootloader_ignore_signals=False,strip=False,upx=True,console=True)
