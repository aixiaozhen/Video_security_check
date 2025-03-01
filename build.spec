# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.building.build_main import Analysis, PYZ, EXE

# 使用绝对路径
BASE_DIR = os.path.abspath(os.getcwd())
FFMPEG_PATH = os.path.join(BASE_DIR, 'bin', 'ffmpeg.exe')

# 检查 ffmpeg.exe 是否存在
ffmpeg_path = Path(FFMPEG_PATH)
if not ffmpeg_path.exists():
    print(f"错误: 找不到 ffmpeg.exe，请确保它位于 {ffmpeg_path.absolute()}")
    sys.exit(1)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[BASE_DIR],
    binaries=[
        (FFMPEG_PATH, 'bin')  # 确保 ffmpeg.exe 被打包到 bin 目录
    ],
    datas=[],
    hiddenimports=[
        'packaging.version',
        'packaging.specifiers',
        'packaging.requirements',
        'packaging.markers'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=2,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,        # 添加二进制文件
    a.zipfiles,        # 添加压缩文件
    a.datas,           # 添加数据文件
    [],
    name='视频安全检查工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='./img/logo.ico'  # 指定图标路径
) 